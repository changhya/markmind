import asyncio
import json
import re
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai.llm import extract_wiki_pages, generate_response
from ai.parser import parse_document
from database.chroma import get_collection
from database.sqlite import db, init_db, new_id, now_iso
from routers import documents, stats, wiki
from routers.chat_history import router as chat_history_router

STORAGE_DIR = Path.home() / ".markmind" / "data" / "files"
WIKI_DIR    = Path.home() / ".markmind" / "data" / "wiki"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
WIKI_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MarkMind Local API",
    description="Local backend for MarkMind Edge AI (LLM-wiki)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(wiki.router)
app.include_router(stats.router)
app.include_router(chat_history_router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return chunks


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def _build_rag_context(query: str, n_results: int = 3):
    collection   = get_collection("wiki_pages")
    results      = collection.query(query_texts=[query], n_results=n_results)
    context_docs = results.get("documents", [[]])[0]
    metadatas    = results.get("metadatas",  [[]])[0]
    return context_docs, metadatas


def _build_chat_prompt(query: str, context_docs: list[str]) -> str:
    context = "\n\n---\n\n".join(context_docs)
    return (
        "You are a helpful AI assistant with access to a comprehensive Wiki knowledge base.\n"
        "Answer the user's question based ONLY on the provided Wiki context.\n"
        "If the answer is not in the context, say "
        "'I cannot answer this based on the provided wiki documents.'\n\n"
        f"Wiki Context:\n{context}\n\n"
        f"Question: {query}"
    )


# ---------------------------------------------------------------------------
# index.md + log.md 생성 (Karpathy LLM-wiki 핵심 구조)
# ---------------------------------------------------------------------------

def _update_index_md(wiki_dir: Path) -> None:
    """전체 위키 페이지를 카테고리별로 정리한 index.md 생성/갱신."""
    with db() as conn:
        pages = conn.execute(
            "SELECT title, summary, tags FROM wiki_pages "
            "WHERE title NOT IN ('index', 'log') ORDER BY title"
        ).fetchall()

    if not pages:
        return

    categories: dict[str, list[dict]] = {}
    for p in pages:
        row = dict(p)
        try:
            tags = json.loads(row["tags"] or "[]")
        except Exception:
            tags = []
        cat = tags[0] if tags else "General"
        categories.setdefault(cat, []).append({**row, "tags": tags})

    lines = [
        "# MarkMind Wiki Index",
        "",
        f"> 마지막 업데이트: {now_iso()[:19]}",
        f"> 총 {len(pages)}개 페이지",
        "",
    ]
    for cat in sorted(categories):
        lines.append(f"## {cat}")
        for p in sorted(categories[cat], key=lambda x: x["title"]):
            summary = (p["summary"] or "")[:80]
            lines.append(f"- [[{p['title']}]]: {summary}")
        lines.append("")

    (wiki_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _append_log_entry(
    wiki_dir: Path,
    filename: str,
    created: int,
    updated: int,
    total_chunks: int,
) -> None:
    """log.md에 Ingest 이벤트를 append-only로 기록."""
    log_path = wiki_dir / "log.md"
    header = "# MarkMind Activity Log\n\n" if not log_path.exists() else ""
    entry = (
        f"## [{now_iso()[:19]}] ingest | {filename}\n"
        f"- 청크 처리: {total_chunks}개\n"
        f"- 생성: {created}개 위키 페이지\n"
        f"- 업데이트: {updated}개 위키 페이지\n\n"
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(header + entry)


def _log_query(wiki_dir: Path, query: str, response_preview: str) -> None:
    """log.md에 Query 이벤트를 기록."""
    log_path = wiki_dir / "log.md"
    header = "# MarkMind Activity Log\n\n" if not log_path.exists() else ""
    entry = (
        f"## [{now_iso()[:19]}] query\n"
        f"- 질문: {query[:100]}\n"
        f"- 답변 미리보기: {response_preview[:100]}\n\n"
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(header + entry)


# ---------------------------------------------------------------------------
# 기존 위키 페이지 컨텍스트 빌더
# ---------------------------------------------------------------------------

def _build_existing_context() -> tuple[str, list[dict]]:
    """현재 위키 페이지 목록을 LLM 프롬프트용 문자열로 변환."""
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title, summary FROM wiki_pages "
            "WHERE title NOT IN ('index', 'log') ORDER BY title"
        ).fetchall()
    pages = [dict(r) for r in rows]
    if not pages:
        return "None yet (this is the first ingest)", pages
    ctx = "\n".join(
        f"- [[{p['title']}]]: {(p['summary'] or 'No summary')[:80]}"
        for p in pages
    )
    return ctx, pages


def _find_page_by_title(title: str, existing: list[dict]) -> dict | None:
    """대소문자 무관 + 부분 일치로 기존 페이지를 찾습니다."""
    tl = title.lower().strip()
    # 1. 정확히 일치
    for p in existing:
        if p["title"].lower().strip() == tl:
            return p
    # 2. 부분 일치
    for p in existing:
        if tl in p["title"].lower() or p["title"].lower() in tl:
            return p
    return None


# ---------------------------------------------------------------------------
# Background document-processing task (Karpathy-aligned Ingest)
# ---------------------------------------------------------------------------

def _process_document(doc_id: str, file_path: str, filename: str, save_dir: Path) -> None:
    """
    Karpathy LLM-wiki Ingest 오퍼레이션:
    1. 문서 파싱 (MarkItDown)
    2. 청킹
    3. 기존 위키 페이지 컨텍스트 수집
    4. 청크별 LLM 추출 (기존 페이지 인식 + [[wikilinks]] 생성)
    5. UPDATE(기존 페이지 보강) or CREATE(신규 페이지)
    6. index.md · log.md 갱신
    """

    def _set_progress(progress: int, wiki_count: int = 0, status: str = "processing") -> None:
        with db() as conn:
            conn.execute(
                "UPDATE documents SET status=?,progress=?,wiki_pages_count=?,updated_at=? WHERE id=?",
                (status, progress, wiki_count, now_iso(), doc_id),
            )

    try:
        _set_progress(5)
        parsed_text = parse_document(file_path)
        _set_progress(15)

        chunks     = chunk_text(parsed_text)
        total      = max(len(chunks), 1)
        collection = get_collection("wiki_pages")
        created_count = 0
        updated_count = 0

        for idx, chunk in enumerate(chunks):
            if len(chunk.strip()) < 100:
                _set_progress(15 + int((idx + 1) / total * 75), created_count + updated_count)
                continue

            # ── 기존 위키 페이지 컨텍스트를 매 청크마다 갱신 ──
            existing_context, existing_pages = _build_existing_context()

            pages = extract_wiki_pages(
                chunk,
                source_name=filename,
                existing_context=existing_context,
            )

            for page in pages:
                title        = page.get("title", "Untitled")
                summary      = page.get("summary", "")
                tags         = page.get("tags", [])
                content      = page.get("content", "")
                updates_title = page.get("updates_existing")

                safe_title = sanitize_filename(title)
                if not safe_title:
                    continue

                ts = now_iso()

                # ── UPDATE: 기존 페이지 보강 ──
                if updates_title:
                    target = _find_page_by_title(updates_title, existing_pages)
                    if target:
                        with db() as conn:
                            existing = conn.execute(
                                "SELECT * FROM wiki_pages WHERE id=?", (target["id"],)
                            ).fetchone()

                        if existing:
                            ex = dict(existing)
                            existing_content = ex.get("content", "")
                            existing_tags    = json.loads(ex.get("tags", "[]"))

                            # 새 정보를 섹션으로 병합
                            merged_content = (
                                existing_content.rstrip()
                                + f"\n\n---\n\n## {filename}에서 추가된 내용\n\n"
                                + content
                            )
                            merged_tags = list(set(existing_tags + tags))
                            new_summary = summary if summary else ex.get("summary", "")

                            # 이전 버전 스냅샷
                            with db() as conn:
                                conn.execute(
                                    "INSERT INTO wiki_revisions "
                                    "(id,wiki_page_id,content,summary,revised_by,created_at) "
                                    "VALUES (?,?,?,?,'agent',?)",
                                    (new_id(), target["id"], existing_content, ex.get("summary"), ts),
                                )
                                conn.execute(
                                    "UPDATE wiki_pages "
                                    "SET summary=?,content=?,tags=?,updated_at=? WHERE id=?",
                                    (new_summary, merged_content, json.dumps(merged_tags), ts, target["id"]),
                                )

                            # 파일 갱신
                            file_path_wiki = ex.get("file_path")
                            if file_path_wiki:
                                try:
                                    fm = (
                                        f'---\ntitle: "{ex["title"]}"\n'
                                        f'summary: "{new_summary}"\n'
                                        f"tags: {merged_tags}\n"
                                        f'last_updated: "{ts}"\n---\n'
                                    )
                                    Path(file_path_wiki).write_text(
                                        fm + "\n\n" + merged_content, encoding="utf-8"
                                    )
                                except OSError:
                                    pass

                            # ChromaDB 갱신
                            chroma_id = ex.get("chroma_id")
                            if chroma_id:
                                try:
                                    collection.update(
                                        ids=[chroma_id],
                                        documents=[merged_content],
                                        metadatas=[{
                                            "title": ex["title"],
                                            "summary": new_summary,
                                            "source": filename,
                                            "tags": ",".join(merged_tags),
                                            "wiki_id": target["id"],
                                        }],
                                    )
                                except Exception:
                                    pass

                            updated_count += 1
                            _set_progress(
                                15 + int((idx + 1) / total * 75),
                                created_count + updated_count,
                            )
                            continue  # 다음 page로

                # ── CREATE: 신규 페이지 ──
                wiki_id   = new_id()
                chroma_id = new_id()

                frontmatter = (
                    f'---\ntitle: "{title}"\nsummary: "{summary}"\n'
                    f"tags: {tags}\nlast_updated: \"{ts}\"\n"
                    f'sources: ["{filename}"]\n---\n'
                )
                full_content = frontmatter + "\n\n" + content
                wiki_file    = save_dir / f"{safe_title}.md"
                wiki_file.write_text(full_content, encoding="utf-8")

                with db() as conn:
                    conn.execute(
                        "INSERT INTO wiki_pages "
                        "(id,title,summary,tags,content,file_path,document_id,chroma_id,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (wiki_id, title, summary, json.dumps(tags), content,
                         str(wiki_file), doc_id, chroma_id, ts, ts),
                    )

                collection.add(
                    documents=[full_content],
                    metadatas=[{
                        "title":   title,
                        "summary": summary,
                        "source":  filename,
                        "tags":    ",".join(tags),
                        "wiki_id": wiki_id,
                    }],
                    ids=[chroma_id],
                )
                created_count += 1

            _set_progress(
                15 + int((idx + 1) / total * 75),
                created_count + updated_count,
            )

        total_wiki = created_count + updated_count

        # LLM이 0개 생성한 경우 경고 메시지
        valid_chunks = sum(1 for c in chunks if len(c.strip()) >= 100)
        if total_wiki == 0 and valid_chunks > 0:
            with db() as conn:
                conn.execute(
                    "UPDATE documents SET error_message=?,updated_at=? WHERE id=?",
                    (
                        f"LLM이 위키 페이지를 생성하지 못했습니다 ({valid_chunks}개 청크 처리). "
                        "Ollama 모델 확인: ollama pull llama3",
                        now_iso(), doc_id,
                    ),
                )

        _set_progress(100, total_wiki, "done")

        # ── 2순위: index.md + log.md 갱신 ──
        try:
            _update_index_md(save_dir)
            _append_log_entry(save_dir, filename, created_count, updated_count, total)
        except Exception:
            pass

    except Exception as exc:
        with db() as conn:
            conn.execute(
                "UPDATE documents SET status='error',error_message=?,updated_at=? WHERE id=?",
                (str(exc), now_iso(), doc_id),
            )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_wiki_dir: str = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    doc_id    = new_id()
    file_path = STORAGE_DIR / file.filename
    save_dir  = Path(target_wiki_dir) if target_wiki_dir else WIKI_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    ts = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO documents "
            "(id,filename,original_path,file_size,mime_type,status,progress,wiki_pages_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,'pending',0,0,?,?)",
            (doc_id, file.filename, str(file_path), file_path.stat().st_size, file.content_type, ts, ts),
        )

    background_tasks.add_task(_process_document, doc_id, str(file_path), file.filename, save_dir)
    return {"status": "processing", "document_id": doc_id, "message": f"{file.filename} 처리가 시작되었습니다."}


# ---------------------------------------------------------------------------
# Chat (standard + streaming)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str
    model: str = "llama3.2:1b"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        context_docs, metadatas = _build_rag_context(request.query)
        if not context_docs:
            return {"query": request.query, "response": "관련 위키 문서를 찾을 수 없습니다.",
                    "context_used": [], "sources": []}

        response = generate_response(
            _build_chat_prompt(request.query, context_docs),
            model_name=request.model,
        )
        sources = [{"title": m.get("title", ""), "source": m.get("source", "")} for m in metadatas]

        ts = now_iso()
        with db() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id,query,response,sources,context_used,model,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id(), request.query, response,
                 json.dumps(sources), json.dumps(context_docs), request.model, ts),
            )

        try:
            _log_query(WIKI_DIR, request.query, response)
        except Exception:
            pass

        return {"query": request.query, "response": response,
                "context_used": context_docs, "sources": sources}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 스트리밍 채팅."""
    context_docs, metadatas = _build_rag_context(request.query)
    sources = [{"title": m.get("title", ""), "source": m.get("source", "")} for m in metadatas]
    full_prompt = _build_chat_prompt(request.query, context_docs) if context_docs else request.query

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_ollama():
        try:
            import ollama as _ollama
            stream = _ollama.chat(
                model=request.model,
                messages=[{"role": "user", "content": full_prompt}],
                stream=True,
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                asyncio.run_coroutine_threadsafe(queue.put(token), loop)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    threading.Thread(target=_run_ollama, daemon=True).start()

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'sources': sources, 'context_used': context_docs})}\n\n"

        accumulated = ""
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=600.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'error': 'LLM timeout'})}\n\n"
                break

            if item is None:
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'error': str(item)})}\n\n"
                break

            accumulated += item
            yield f"data: {json.dumps({'token': item})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

        ts = now_iso()
        with db() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id,query,response,sources,context_used,model,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id(), request.query, accumulated,
                 json.dumps(sources), json.dumps(context_docs), request.model, ts),
            )
        try:
            _log_query(WIKI_DIR, request.query, accumulated)
        except Exception:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"status": "ok", "message": "MarkMind Local Backend is running", "storage": str(STORAGE_DIR)}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
