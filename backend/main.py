import uuid
import shutil
from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from pydantic import BaseModel
import re

from ai.parser import parse_document
from ai.llm import generate_response, extract_wiki_pages
from database.chroma import get_collection

# MarkMind Local Storage Paths
STORAGE_DIR = Path.home() / ".markmind" / "data" / "files"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

WIKI_DIR = Path.home() / ".markmind" / "data" / "wiki"
WIKI_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MarkMind Local API", description="Local backend for MarkMind Edge AI (LLM-wiki)")

# Tauri 프론트엔드와의 통신을 위한 CORS 설정 (로컬 환경)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    model: str = "llama3"

def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """텍스트를 일정한 크기의 청크로 분할합니다."""
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def sanitize_filename(name: str) -> str:
    """파일명으로 사용할 수 없는 문자를 제거합니다."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "MarkMind Local Backend is running", "storage": str(STORAGE_DIR)}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), target_wiki_dir: str = Form(None)):
    """
    파일을 업로드하고, 파싱(MarkItDown)한 뒤 LLM-wiki 방식으로 지식을 추출하여 저장합니다.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = STORAGE_DIR / file.filename
    try:
        # 1. 파일 로컬 저장 (원천 데이터 보존)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. 파일 파싱 (MarkItDown)
        parsed_text = parse_document(str(file_path))
        
        # 3. 텍스트 청킹
        chunks = chunk_text(parsed_text)
        
        collection = get_collection("wiki_pages")
        created_pages_count = 0
        
        # Determine the target directory for wiki pages
        save_dir = Path(target_wiki_dir) if target_wiki_dir else WIKI_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. LLM을 이용한 지식 추출 (Wiki 페이지 생성)
        for chunk in chunks:
            if len(chunk.strip()) < 100:
                continue
                
            wiki_pages = extract_wiki_pages(chunk, source_name=file.filename)
            
            for page in wiki_pages:
                title = page.get("title", "Untitled")
                summary = page.get("summary", "")
                tags = page.get("tags", [])
                content = page.get("content", "")
                
                safe_title = sanitize_filename(title)
                if not safe_title:
                    continue
                    
                now_str = datetime.now().isoformat()
                
                # YAML Frontmatter 구성
                frontmatter = f"""---
title: "{title}"
summary: "{summary}"
tags: {tags}
last_updated: "{now_str}"
sources: ["{file.filename}"]
---
"""
                full_wiki_content = f"{frontmatter}\n\n{content}"
                
                # 5. Wiki Markdown 파일 저장 (로컬 파일 시스템)
                wiki_file_path = save_dir / f"{safe_title}.md"
                with open(wiki_file_path, "w", encoding="utf-8") as f:
                    f.write(full_wiki_content)
                
                # 6. ChromaDB 인덱싱 (하이브리드 검색 기반 마련)
                page_id = str(uuid.uuid4())
                metadata = {
                    "title": title,
                    "summary": summary,
                    "source": file.filename,
                    "tags": ",".join(tags)
                }
                
                collection.add(
                    documents=[full_wiki_content],
                    metadatas=[metadata],
                    ids=[page_id]
                )
                
                created_pages_count += 1
        
        return {
            "status": "success", 
            "message": f"Successfully processed and stored {file.filename}",
            "wiki_pages_created": created_pages_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    사용자의 질문을 바탕으로 ChromaDB에서 관련 위키 문서를 검색하고 (RAG),
    Ollama를 통해 답변을 생성합니다.
    """
    try:
        query = request.query
        
        # 1. ChromaDB에서 관련 위키 문서 검색
        collection = get_collection("wiki_pages")
        results = collection.query(
            query_texts=[query],
            n_results=3  # 상위 3개 위키 문서 검색
        )
        
        # 검색된 위키 문서 가져오기
        context_texts = results.get("documents", [[]])[0]
        
        if not context_texts:
            return {"query": query, "response": "관련 위키 문서를 찾을 수 없습니다.", "context_used": []}

        context = "\n\n---\n\n".join(context_texts)
        
        # 2. 프롬프트 구성 (RAG)
        system_prompt = (
            "You are a helpful AI assistant with access to a comprehensive Wiki knowledge base.\n"
            "Answer the user's question based ONLY on the provided Wiki context.\n"
            "If the answer is not in the context, say 'I cannot answer this based on the provided wiki documents.'\n\n"
            "Wiki Context:\n"
            f"{context}\n\n"
        )
        
        full_prompt = f"{system_prompt}Question: {query}"
        
        # 3. Ollama로 응답 생성
        response = generate_response(full_prompt, model_name=request.model)
        
        return {
            "query": query,
            "response": response,
            "context_used": context_texts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
