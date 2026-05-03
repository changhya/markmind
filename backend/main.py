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
    """Query ChromaDB and return (context_docs, metadatas, full_context_str)."""
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
# Background document-processing task
# ---------------------------------------------------------------------------

def _process_document(doc_id: str, file_path: str, filename: str, save_dir: Path) -> None:
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
        wiki_count = 0

        for idx, chunk in enumerate(chunks):
            if len(chunk.strip()) < 100:
                continue

            for page in extract_wiki_pages(chunk, source_name=filename):
                title   = page.get("title", "Untitled")
                summary = page.get("summary", "")
                tags    = page.get("tags", [])
                content = page.get("content", "")

                safe_title = sanitize_filename(title)
                if not safe_title:
                    continue

                ts        = now_iso()
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
                    metadatas=[{"title": title, "summary": summary,
                                "source": filename, "tags": ",".join(tags), "wiki_id": wiki_id}],
                    ids=[chroma_id],
                )
                wiki_count += 1

            _set_progress(15 + int((idx + 1) / total * 75), wiki_count)

        _set_progress(100, wiki_count, "done")

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

    doc_id   = new_id()
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
    model: str = "llama3"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        context_docs, metadatas = _build_rag_context(request.query)
        if not context_docs:
            return {"query": request.query, "response": "관련 위키 문서를 찾을 수 없습니다.",
                    "context_used": [], "sources": []}

        response = generate_response(_build_chat_prompt(request.query, context_docs),
                                     model_name=request.model)
        sources  = [{"title": m.get("title", ""), "source": m.get("source", "")} for m in metadatas]

        # Persist chat session
        ts = now_iso()
        with db() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id,query,response,sources,context_used,model,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id(), request.query, response,
                 json.dumps(sources), json.dumps(context_docs), request.model, ts),
            )

        return {"query": request.query, "response": response,
                "context_used": context_docs, "sources": sources}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming chat: tokens arrive token-by-token from Ollama."""
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
        # Emit RAG context metadata first
        yield f"data: {json.dumps({'sources': sources, 'context_used': context_docs})}\n\n"

        accumulated = ""
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=120.0)
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

        # Persist session after stream ends
        ts = now_iso()
        with db() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id,query,response,sources,context_used,model,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id(), request.query, accumulated,
                 json.dumps(sources), json.dumps(context_docs), request.model, ts),
            )

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
