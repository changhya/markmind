import os
import time
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

API_URL = "http://127.0.0.1:8000/api/upload"

class DocumentWatcher(FileSystemEventHandler):
    def __init__(self, target_wiki_dir: str):
        self.target_wiki_dir = target_wiki_dir
        super().__init__()

    def process_file(self, file_path):
        if not os.path.isfile(file_path):
            return
        
        # 제외할 파일 확장자 처리
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".tmp", ".crdownload"]:
            return
            
        print(f"\n[Watcher] New file detected: {file_path}")
        print(f"Uploading to server with target wiki dir: {self.target_wiki_dir}...")
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                data = {"target_wiki_dir": self.target_wiki_dir} if self.target_wiki_dir else {}
                
                response = requests.post(API_URL, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"Success! {result.get('message')}")
                    print(f"Created {result.get('wiki_pages_created')} wiki pages.")
                else:
                    print(f"Failed to process file. Server returned {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    def on_created(self, event):
        # 파일이 생성되자마자 복사가 덜 끝났을 수 있으므로 약간 대기
        time.sleep(1)
        self.process_file(event.src_path)

def start_watching(watch_dir: str, target_wiki_dir: str = None):
    """
    특정 폴더(watch_dir)를 감시하다가 새 문서가 들어오면
    백엔드로 전송하여 LLM-wiki(target_wiki_dir)로 변환/축적합니다.
    """
    watch_path = Path(watch_dir)
    watch_path.mkdir(parents=True, exist_ok=True)
    
    if target_wiki_dir:
        wiki_path = Path(target_wiki_dir)
        wiki_path.mkdir(parents=True, exist_ok=True)
        print(f"Accumulating Wiki pages into: {wiki_path.absolute()}")
    else:
        print("Accumulating Wiki pages into the default ~/.markmind/data/wiki directory.")
        
    print(f"Monitoring directory: {watch_path.absolute()}")
    print("Drop PDF/Word/Markdown files here to auto-process them. Press Ctrl+C to stop.")
    
    event_handler = DocumentWatcher(target_wiki_dir)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Watch a directory and upload documents to MarkMind Backend.")
    parser.add_argument("--watch-dir", "-w", default=str(Path.home() / "Desktop" / "MarkMind_Inbox"), 
                        help="Directory to monitor for new files")
    parser.add_argument("--wiki-dir", "-d", default=None, 
                        help="Target directory to accumulate generated Wiki Markdown files")
    
    args = parser.parse_args()
    start_watching(args.watch_dir, args.wiki_dir)
