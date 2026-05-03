import json
from pathlib import Path

from fastapi import APIRouter

from database.sqlite import DB_PATH, db

router = APIRouter(prefix="/api/stats", tags=["stats"])

_CHROMA_DIR = Path.home() / ".markmind" / "data" / "chroma"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


@router.get("")
def get_stats():
    with db() as conn:
        total_docs  = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        total_wiki  = conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]

        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM documents GROUP BY status"
        ).fetchall()
        documents_by_status = {r["status"]: r["cnt"] for r in status_rows}

        recent_docs = conn.execute(
            "SELECT id, filename, status, progress, wiki_pages_count, created_at "
            "FROM documents ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

        recent_wiki_rows = conn.execute(
            "SELECT id, title, summary, tags, created_at "
            "FROM wiki_pages ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

    recent_wiki = []
    for r in recent_wiki_rows:
        item = dict(r)
        try:
            item["tags"] = json.loads(item["tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            item["tags"] = []
        recent_wiki.append(item)

    return {
        "total_documents":     total_docs,
        "total_wiki_pages":    total_wiki,
        "documents_by_status": documents_by_status,
        "db_size_bytes":       DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "chroma_size_bytes":   _dir_size(_CHROMA_DIR),
        "recent_documents":    [dict(r) for r in recent_docs],
        "recent_wiki_pages":   recent_wiki,
    }
