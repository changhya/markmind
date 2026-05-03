import os

from fastapi import APIRouter, HTTPException

from database.chroma import get_collection
from database.sqlite import db

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{doc_id}/status")
def get_document_status(doc_id: str):
    with db() as conn:
        row = conn.execute(
            "SELECT id, status, progress, wiki_pages_count, error_message "
            "FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    with db() as conn:
        doc_row = conn.execute(
            "SELECT original_path FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")

        wiki_rows = conn.execute(
            "SELECT file_path, chroma_id FROM wiki_pages WHERE document_id = ?",
            (doc_id,),
        ).fetchall()

        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    # Remove ChromaDB entries
    chroma_ids = [r["chroma_id"] for r in wiki_rows if r["chroma_id"]]
    if chroma_ids:
        try:
            get_collection("wiki_pages").delete(ids=chroma_ids)
        except Exception:
            pass

    # Remove files from disk
    try:
        os.remove(doc_row["original_path"])
    except OSError:
        pass

    for wiki_row in wiki_rows:
        if wiki_row["file_path"]:
            try:
                os.remove(wiki_row["file_path"])
            except OSError:
                pass

    return {"status": "deleted", "id": doc_id}
