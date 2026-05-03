"""Wiki page CRUD + Stateful AI operations.

Route ordering is intentional: /duplicates and /merge are literal paths
and MUST be defined before /{wiki_id} to avoid FastAPI treating them as IDs.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.chroma import get_collection
from database.sqlite import db, new_id, now_iso
from markmind.llm import get_provider

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_tags(raw: str | None) -> list[str]:
    try:
        return json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def _build_tree(pages: list[dict]) -> list[dict]:
    page_map = {p["id"]: {**p, "children": []} for p in pages}
    roots: list[dict] = []
    for page in page_map.values():
        pid = page.get("parent_id")
        if pid and pid in page_map:
            page_map[pid]["children"].append(page)
        else:
            roots.append(page)
    return roots


def _extract_json_dict(text: str) -> dict | None:
    """Extract first JSON object from an LLM response that may contain prose."""
    clean = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()
    match = re.search(r"\{[\s\S]*\}", clean)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _sync_page_to_disk(file_path: str | None, title: str, summary: str | None,
                       tags: list, content: str, ts: str) -> None:
    if not file_path:
        return
    try:
        fm = (
            f'---\ntitle: "{title}"\n'
            f'summary: "{summary or ""}"\n'
            f"tags: {tags}\n"
            f'last_updated: "{ts}"\n---\n'
        )
        Path(file_path).write_text(fm + "\n\n" + content, encoding="utf-8")
    except OSError:
        pass


def _sync_page_to_chroma(chroma_id: str | None, title: str, summary: str | None,
                          tags: list, content: str) -> None:
    if not chroma_id:
        return
    try:
        get_collection("wiki_pages").update(
            ids=[chroma_id],
            documents=[content],
            metadatas=[{
                "title": title,
                "summary": summary or "",
                "tags": ",".join(tags),
            }],
        )
    except Exception:
        pass


# ── Pydantic models ───────────────────────────────────────────────────────────

class WikiPageUpdate(BaseModel):
    title:   Optional[str]       = None
    summary: Optional[str]       = None
    content: Optional[str]       = None
    tags:    Optional[list[str]] = None


class RefineRequest(BaseModel):
    context: Optional[str] = None  # additional text to incorporate


class MergeRequest(BaseModel):
    source_ids: list[str]         # IDs to merge (≥ 2)
    keep_id:    Optional[str] = None  # which ID to keep (defaults to first)


# ── Static routes (must come before /{wiki_id}) ───────────────────────────────

@router.get("")
def list_wiki_pages(flat: bool = False):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title, summary, tags, parent_id, document_id, "
            "file_path, created_at, updated_at FROM wiki_pages ORDER BY title ASC"
        ).fetchall()
    pages = [{**dict(r), "tags": _parse_tags(r["tags"])} for r in rows]
    return pages if flat else _build_tree(pages)


@router.get("/duplicates")
def find_duplicates(threshold: float = 0.30):
    """Return clusters of wiki pages that appear semantically similar."""
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title, chroma_id FROM wiki_pages WHERE chroma_id IS NOT NULL"
        ).fetchall()
    pages = [dict(r) for r in rows]

    if len(pages) < 2:
        return []

    collection = get_collection("wiki_pages")
    seen:   set[str]   = set()
    groups: list[dict] = []

    for page in pages:
        if page["id"] in seen:
            continue
        try:
            results = collection.query(
                query_texts=[page["title"]],
                n_results=min(6, len(pages)),
                include=["distances", "metadatas"],
            )
        except Exception:
            continue

        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        similar = [
            {"id": m.get("wiki_id"), "distance": round(d, 4)}
            for d, m in zip(distances, metadatas)
            if m.get("wiki_id") and m["wiki_id"] != page["id"] and d < threshold
        ]

        if similar:
            groups.append({"source": {"id": page["id"], "title": page["title"]}, "similar": similar})
            seen.add(page["id"])
            for s in similar:
                seen.add(s["id"])

    return groups


@router.post("/merge")
def merge_wiki_pages(request: MergeRequest):
    """LLM-based merge of 2+ wiki pages into one."""
    if len(request.source_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 source_ids to merge")

    with db() as conn:
        pages_data = []
        for pid in request.source_ids:
            row = conn.execute("SELECT * FROM wiki_pages WHERE id=?", (pid,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Wiki page {pid} not found")
            pages_data.append(dict(row))

    pages_text = "\n\n---\n\n".join(
        f"### Page {i+1}: {p['title']}\n{p.get('content', '')}"
        for i, p in enumerate(pages_data)
    )
    prompt = (
        f"Merge the following {len(pages_data)} wiki pages into one comprehensive page.\n\n"
        f"{pages_text}\n\n"
        "Instructions: combine all information without duplication, create clear structure.\n"
        'Respond with ONLY a JSON object:\n'
        '{"title":"...","summary":"one sentence","tags":["t1","t2"],"content":"markdown"}'
    )

    try:
        provider = get_provider()
        raw = provider.generate(prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM error: {exc}")

    merged = _extract_json_dict(raw)
    if not merged:
        raise HTTPException(status_code=422, detail="LLM returned no parseable JSON")

    keep_id  = request.keep_id or request.source_ids[0]
    new_tags = json.dumps(merged.get("tags", []))
    ts       = now_iso()

    with db() as conn:
        # Update the kept page
        conn.execute(
            "UPDATE wiki_pages SET title=?,summary=?,content=?,tags=?,updated_at=? WHERE id=?",
            (merged["title"], merged.get("summary"), merged.get("content", ""), new_tags, ts, keep_id),
        )
        kept = dict(conn.execute("SELECT * FROM wiki_pages WHERE id=?", (keep_id,)).fetchone())

        # Delete other pages (ChromaDB + disk + DB)
        for pid in request.source_ids:
            if pid == keep_id:
                continue
            other = conn.execute("SELECT chroma_id, file_path FROM wiki_pages WHERE id=?", (pid,)).fetchone()
            if other:
                if other["chroma_id"]:
                    try: get_collection("wiki_pages").delete(ids=[other["chroma_id"]])
                    except Exception: pass
                if other["file_path"]:
                    try: os.remove(other["file_path"])
                    except OSError: pass
            conn.execute("DELETE FROM wiki_pages WHERE id=?", (pid,))

    tags_list = merged.get("tags", [])
    _sync_page_to_disk(kept.get("file_path"), merged["title"], merged.get("summary"), tags_list, merged.get("content", ""), ts)
    _sync_page_to_chroma(kept.get("chroma_id"), merged["title"], merged.get("summary"), tags_list, merged.get("content", ""))

    return {"status": "merged", "id": keep_id, "title": merged["title"], "merged_count": len(request.source_ids)}


# ── Parameterised routes ──────────────────────────────────────────────────────

@router.get("/{wiki_id}")
def get_wiki_page(wiki_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM wiki_pages WHERE id=?", (wiki_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    page = dict(row)
    page["tags"] = _parse_tags(page["tags"])
    return page


@router.put("/{wiki_id}")
def update_wiki_page(wiki_id: str, update: WikiPageUpdate):
    with db() as conn:
        row = conn.execute("SELECT * FROM wiki_pages WHERE id=?", (wiki_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        current = dict(row)

        conn.execute(
            "INSERT INTO wiki_revisions (id,wiki_page_id,content,summary,revised_by,created_at) "
            "VALUES (?,?,?,?,'user',?)",
            (new_id(), wiki_id, current["content"], current["summary"], now_iso()),
        )

        new_title   = update.title   if update.title   is not None else current["title"]
        new_summary = update.summary if update.summary is not None else current["summary"]
        new_content = update.content if update.content is not None else current["content"]
        new_tags    = json.dumps(update.tags) if update.tags is not None else current["tags"]
        ts = now_iso()

        conn.execute(
            "UPDATE wiki_pages SET title=?,summary=?,content=?,tags=?,updated_at=? WHERE id=?",
            (new_title, new_summary, new_content, new_tags, ts, wiki_id),
        )

    tags_list = json.loads(new_tags) if isinstance(new_tags, str) else (new_tags or [])
    _sync_page_to_disk(current.get("file_path"), new_title, new_summary, tags_list, new_content, ts)
    _sync_page_to_chroma(current.get("chroma_id"), new_title, new_summary, tags_list, new_content)

    return {"status": "updated", "id": wiki_id, "updated_at": ts}


@router.post("/{wiki_id}/refine")
def refine_wiki_page(wiki_id: str, request: RefineRequest):
    """Agent refines an existing wiki page, optionally incorporating new context."""
    with db() as conn:
        row = conn.execute("SELECT * FROM wiki_pages WHERE id=?", (wiki_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        current = dict(row)

    tags_list = _parse_tags(current.get("tags"))
    context_block = f"\nNEW CONTEXT TO INCORPORATE:\n{request.context}" if request.context else ""

    prompt = (
        "You are a knowledge expert. Refine and improve the following wiki page.\n\n"
        f"CURRENT PAGE:\nTitle: {current['title']}\nTags: {tags_list}\n"
        f"Content:\n{current.get('content', '')}\n"
        f"{context_block}\n\n"
        "Improve clarity, structure, and completeness. Update tags if needed.\n"
        'Respond with ONLY a JSON object:\n'
        '{"title":"...","summary":"one sentence","tags":["t1"],"content":"full markdown"}'
    )

    try:
        provider = get_provider()
        raw = provider.generate(prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM error: {exc}")

    refined = _extract_json_dict(raw)
    if not refined:
        raise HTTPException(status_code=422, detail="LLM returned no parseable JSON")

    ts       = now_iso()
    new_tags = json.dumps(refined.get("tags", []))

    with db() as conn:
        # Snapshot current version before overwriting
        conn.execute(
            "INSERT INTO wiki_revisions (id,wiki_page_id,content,summary,revised_by,created_at) "
            "VALUES (?,?,?,?,'agent',?)",
            (new_id(), wiki_id, current["content"], current.get("summary"), ts),
        )
        conn.execute(
            "UPDATE wiki_pages SET title=?,summary=?,content=?,tags=?,updated_at=? WHERE id=?",
            (refined["title"], refined.get("summary"), refined.get("content", ""), new_tags, ts, wiki_id),
        )

    tags_result = refined.get("tags", [])
    _sync_page_to_disk(current.get("file_path"), refined["title"], refined.get("summary"), tags_result, refined.get("content", ""), ts)
    _sync_page_to_chroma(current.get("chroma_id"), refined["title"], refined.get("summary"), tags_result, refined.get("content", ""))

    return {
        "status":     "refined",
        "id":         wiki_id,
        "title":      refined["title"],
        "updated_at": ts,
    }


@router.get("/{wiki_id}/revisions")
def get_wiki_revisions(wiki_id: str):
    with db() as conn:
        if not conn.execute("SELECT id FROM wiki_pages WHERE id=?", (wiki_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Wiki page not found")
        rows = conn.execute(
            "SELECT * FROM wiki_revisions WHERE wiki_page_id=? ORDER BY created_at DESC",
            (wiki_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.delete("/{wiki_id}")
def delete_wiki_page(wiki_id: str):
    with db() as conn:
        row = conn.execute(
            "SELECT file_path, chroma_id FROM wiki_pages WHERE id=?", (wiki_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        conn.execute("DELETE FROM wiki_pages WHERE id=?", (wiki_id,))

    if row["chroma_id"]:
        try: get_collection("wiki_pages").delete(ids=[row["chroma_id"]])
        except Exception: pass

    if row["file_path"]:
        try: os.remove(row["file_path"])
        except OSError: pass

    return {"status": "deleted", "id": wiki_id}
