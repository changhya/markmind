from markitdown import MarkItDown
import os

md = MarkItDown()

def parse_document(file_path: str) -> str:
    """
    주어진 파일을 Markdown 형식으로 파싱합니다. (Microsoft MarkItDown 사용)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    result = md.convert(file_path)
    return result.text_content
