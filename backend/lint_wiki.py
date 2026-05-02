import os
import glob
from pathlib import Path

# MarkMind Local Wiki Storage Path
WIKI_DIR = Path.home() / ".markmind" / "data" / "wiki"

def lint_knowledge_base():
    """
    위키 저장소(Markdown 파일)의 무결성을 검사하는 간단한 린팅 스크립트입니다.
    """
    print(f"Starting knowledge linting for directory: {WIKI_DIR}")
    if not WIKI_DIR.exists():
        print("Wiki directory does not exist yet. Please upload documents first.")
        return

    wiki_files = glob.glob(str(WIKI_DIR / "*.md"))
    print(f"Found {len(wiki_files)} wiki pages.")

    orphans_count = 0
    oversized_count = 0
    missing_frontmatter_count = 0

    for file_path in wiki_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split('\n')
            
            # 1. 내용 과밀화 검사
            if len(lines) > 800:
                print(f"[Warning] Oversized page: {os.path.basename(file_path)} ({len(lines)} lines)")
                oversized_count += 1
            
            # 2. 프론트매터 누락 검사
            if not content.startswith("---"):
                print(f"[Warning] Missing frontmatter: {os.path.basename(file_path)}")
                missing_frontmatter_count += 1
            
            # (추가 구현 가능: 깨진 링크 검사, 고립된 페이지 검사 등)
            # 여기서는 단순한 파일 스캔 로직만 포함합니다.

    print("--- Linting Summary ---")
    print(f"Total Pages Checked: {len(wiki_files)}")
    print(f"Oversized Pages (>800 lines): {oversized_count}")
    print(f"Pages Missing Frontmatter: {missing_frontmatter_count}")
    print("Linting completed.")

if __name__ == "__main__":
    lint_knowledge_base()
