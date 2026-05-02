import chromadb
from pathlib import Path

# 로컬 저장소 경로 설정
CHROMA_DB_DIR = Path.home() / ".markmind" / "data" / "chroma"
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# Persistent Client 생성 (로컬에만 저장)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

def get_collection(collection_name: str = "documents"):
    """
    기본 문서 컬렉션을 가져오거나 생성합니다.
    """
    return chroma_client.get_or_create_collection(name=collection_name)
