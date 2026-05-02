# MarkMind

MarkMind는 로컬 환경에서 구동되는 **지능형 문서 자산화 및 LLM-Wiki 플랫폼**입니다. 사용자가 업로드한 문서(PDF 등)를 분석하여 마크다운(Markdown) 기반의 위키 페이지로 자동 변환·저장하며, RAG(검색 증강 생성) 기술을 통해 축적된 지식과 대화할 수 있는 기능을 제공합니다. 

현재 프로토타입은 FastAPI, React, ChromaDB, 그리고 로컬 LLM인 Ollama를 기반으로 동작합니다.

## 🚀 주요 기능

1. **문서 파싱 및 지식 추출 (Upload & Parse)**
   - `MarkItDown`을 활용하여 업로드된 문서를 Markdown으로 변환합니다.
   - 로컬 LLM(Ollama)이 문서 텍스트를 분석하여 핵심 주제를 추출하고, 프론트매터(Frontmatter)가 포함된 개별 위키 페이지(Markdown)로 분할하여 자동 생성합니다.
2. **로컬 지식 저장소 (Local Knowledge Base)**
   - 생성된 위키 파일은 사용자 로컬 PC(`~/.markmind/data/wiki`)에 안전하게 저장됩니다.
   - 검색을 위해 `ChromaDB`에 문서 내용과 메타데이터가 벡터화되어 로컬 저장(`~/.markmind/data/chroma`)됩니다.
3. **RAG 기반 챗봇 (Chat with Data)**
   - 사용자의 질문에 대해 ChromaDB에서 가장 관련된 위키 문서를 검색합니다.
   - 검색된 문맥(Context)을 바탕으로 로컬 LLM이 빠르고 정확한 답변을 생성합니다.

## 🛠️ 기술 스택

- **Backend**: Python, FastAPI, ChromaDB, Ollama, MarkItDown
- **Frontend**: React (TypeScript, Vite), Axios
- **Desktop**: Tauri (예정/진행중)

## 💻 실행 방법 (로컬 개발 환경)

### 사전 요구 사항
- Python 3.10 이상
- Node.js
- **Ollama**: 로컬에 설치 및 실행 중이어야 하며, 기본적으로 `llama3` 모델이 필요합니다. (`ollama run llama3`)

### 1. 백엔드(Backend) 실행
```bash
cd backend
# 가상환경 생성 및 활성화 (선택)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# FastAPI 서버 실행
uvicorn main:app --reload
# 서버는 http://127.0.0.1:8000 에서 실행됩니다.
```

### 2. 프론트엔드(Frontend) 실행
```bash
cd frontend

# 패키지 설치
npm install

# 개발 서버 실행
npm run dev
# 보통 http://localhost:5173 에서 실행됩니다.
```

## 📁 디렉토리 구조

- `backend/`: FastAPI 기반의 API 서버, RAG 로직, LLM 연동 코드
  - `main.py`: 서버 메인 진입점 및 API 라우터 (Upload, Chat)
  - `ai/`: 문서 파싱(`parser.py`) 및 Ollama 연동(`llm.py`) 모듈
  - `database/`: ChromaDB 연동 및 컬렉션 관리(`chroma.py`)
- `frontend/`: React + Vite 기반의 사용자 인터페이스
  - `src/App.tsx`: 파일 업로드 및 채팅 UI
- `src-tauri/`: 향후 데스크톱 앱 패키징을 위한 Tauri 설정 폴더
