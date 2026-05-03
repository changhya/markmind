# MarkMind Edge AI

> **로컬 100% 보안 · 상태 보존형 지식 합성 시스템**  
> 파편화된 비정형 문서를 AI가 자동으로 위키 지식 체계로 전환하고, 축적된 지식과 안전하게 대화합니다.

Andrej Karpathy의 **LLM-Wiki** 철학을 기반으로 설계되었습니다.  
모든 데이터 처리와 모델 추론은 외부 클라우드 통신 없이 온프레미스 환경에서 수행됩니다.

---

## 주요 기능

### 1. Knowledge Ingest — 지능형 문서 파이프라인
- **Drag & Drop 업로드**: PDF, DOCX, PPTX 파일을 드래그하여 즉시 처리 시작
- **비동기 처리**: 업로드 즉시 응답 반환, 백그라운드에서 Parsing → LLM Extraction → Indexing 진행
- **단계별 진행률**: 파이프라인 각 단계의 상태를 실시간으로 시각화
- **MarkItDown 변환**: Microsoft MarkItDown 라이브러리로 비정형 문서를 고품질 Markdown으로 변환

### 2. AI Chat Explorer — 설명 가능한 로컬 RAG
- **SSE 스트리밍**: 응답을 토큰 단위로 실시간 스트리밍 (타이핑 커서 효과)
- **참조 문서 패널**: 답변 생성에 사용된 위키 페이지와 텍스트 청크를 우측 패널에 상시 노출
- **출처 배지**: 각 응답 하단에 참조한 문서명 배지 표시
- **모델 선택**: Ollama에서 pull된 모든 모델 선택 가능 (llama3, mistral, gemma2 등)

### 3. Wiki & Graph — 지식 연결망 탐색
- **트리 사이드바**: 태그 기반 계층 구조로 위키 페이지 탐색
- **Markdown 뷰어**: YAML Frontmatter 칩(태그, 요약) + GFM 렌더링
- **Human-in-the-loop 편집**: 인라인 편집 저장 시 자동으로 이전 버전 스냅샷
- **AI 정제 (Refine)**: 버튼 클릭으로 LLM이 기존 위키 페이지 내용을 개선
- **병합 모드 (Merge)**: 2개 이상 페이지 선택 후 LLM이 하나의 통합 문서로 병합
- **중복 탐지**: ChromaDB 유사도 기반으로 유사 페이지 탐지, 그래프 뷰에서 강조 표시
- **React Flow 지식 그래프**: 공유 태그로 연결된 위키 노드 그래프, 노드 클릭 시 Wiki View로 이동

### 4. Audit Trail — 규제 감사 시스템
- **편집 이력**: 위키 페이지의 모든 변경 사항을 타임라인으로 열람 (사용자 편집 / AI 정제 구분)
- **Chat Why-Trail**: 모든 AI 답변 세션을 보존 — 질문, 응답, 사용된 컨텍스트, 참조 문서를 완전히 추적

### 5. Settings
- Backend URL, 기본 모델, 다크/라이트 모드 설정
- 설정값은 localStorage에 영속화되어 재시작 시에도 유지

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                  Frontend (React + Tailwind)             │
│  IngestPage │ ChatPage │ WikiPage │ AuditPage │ Settings │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API + SSE
┌─────────────────────▼───────────────────────────────────┐
│                   Backend (FastAPI)                      │
│  /api/upload  /api/chat  /api/chat/stream               │
│  /api/documents  /api/wiki  /api/stats                  │
│  /api/wiki/{id}/refine  /api/wiki/merge                 │
│  /api/wiki/duplicates  /api/chat/history                │
└──────────┬──────────────────┬───────────────────────────┘
           │                  │
    ┌──────▼──────┐    ┌──────▼──────┐    ┌─────────────┐
    │   SQLite    │    │  ChromaDB   │    │   Ollama    │
    │  (메타데이터 │    │  (벡터 검색) │    │ (로컬 추론) │
    │  이력, 세션) │    │             │    │             │
    └─────────────┘    └─────────────┘    └─────────────┘
```

### 로컬 저장 경로

| 경로 | 내용 |
|---|---|
| `~/.markmind/data/files/` | 업로드된 원본 문서 |
| `~/.markmind/data/wiki/` | 생성된 위키 Markdown 파일 |
| `~/.markmind/data/chroma/` | ChromaDB 벡터 인덱스 |
| `~/.markmind/data/markmind.db` | SQLite (문서 상태, 위키 메타데이터, 채팅 이력) |

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| **Backend** | Python 3.10+, FastAPI, SQLite (WAL), ChromaDB |
| **AI / LLM** | Ollama (llama3, mistral 등), Microsoft MarkItDown |
| **LLM 추상화** | 자체 `markmind.llm` Provider 패턴 (Claude / Ollama) |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **UI 라이브러리** | React Router v6, React Flow (@xyflow/react), react-markdown |
| **Desktop** | Tauri v2 (예정) |

---

## 실행 방법

### 사전 요구 사항

- Python 3.10 이상
- Node.js 18 이상
- [Ollama](https://ollama.ai) 설치 및 실행

```bash
# Ollama 모델 준비 (최초 1회)
ollama pull llama3
```

### 1. markmind 패키지 설치

```bash
# 프로젝트 루트에서
pip install -e ".[ollama]"

# Claude도 함께 사용하려면
pip install -e ".[all]"
```

### 2. 백엔드 실행

```bash
cd backend

# 가상환경 설정 (권장)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 의존성 설치
pip install fastapi uvicorn chromadb markitdown ollama

# 서버 실행
uvicorn main:app --reload
# → http://127.0.0.1:8000
```

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 환경 변수 (선택)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MARKMIND_DEFAULT_LLM` | `ollama` | 기본 LLM 프로바이더 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 서버 주소 |
| `MARKMIND_OLLAMA_MODEL` | `llama3` | 기본 Ollama 모델 |
| `ANTHROPIC_API_KEY` | (없음) | Claude 프로바이더 사용 시 |
| `MARKMIND_CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude 모델 선택 |

---

## 프로젝트 구조

```
MarkMind/
├── backend/
│   ├── main.py                  # FastAPI 앱, 업로드/채팅/스트리밍 엔드포인트
│   ├── ai/
│   │   ├── parser.py            # MarkItDown 문서 파싱
│   │   └── llm.py               # Legacy 파사드 (markmind.llm으로 위임)
│   ├── database/
│   │   ├── chroma.py            # ChromaDB 클라이언트
│   │   └── sqlite.py            # SQLite 스키마 및 헬퍼 (documents, wiki_pages, wiki_revisions, chat_sessions)
│   └── routers/
│       ├── documents.py         # GET/DELETE /api/documents
│       ├── wiki.py              # CRUD + refine + merge + duplicates
│       ├── stats.py             # GET /api/stats
│       └── chat_history.py      # GET /api/chat/history
│
├── frontend/
│   └── src/
│       ├── api/client.ts        # 전체 API 호출 함수
│       ├── types/index.ts       # 공통 TypeScript 타입
│       ├── contexts/
│       │   └── ThemeContext.tsx  # 다크/라이트 모드
│       ├── components/
│       │   └── Layout.tsx       # 5메뉴 사이드바 레이아웃
│       └── pages/
│           ├── IngestPage.tsx   # 문서 업로드 + 파이프라인 모니터링
│           ├── ChatPage.tsx     # SSE 스트리밍 채팅 + 참조 패널
│           ├── WikiPage.tsx     # 트리 뷰어 + 편집 + AI 정제 + 병합 + React Flow
│           ├── AuditPage.tsx    # 편집 이력 + Chat Why-Trail
│           └── SettingsPage.tsx # 환경 설정
│
├── src/
│   └── markmind/
│       └── llm/                 # LLM Provider 추상화 계층 (ADR-001)
│           ├── base.py          # LLMProvider ABC
│           ├── schemas.py       # WikiPage, GenerateOptions (Pydantic)
│           ├── factory.py       # get_provider() 팩토리
│           ├── claude_provider.py
│           ├── ollama_provider.py
│           └── _parsing.py      # JSON 복구 파서
│
└── docs/
    └── architecture/            # ADR 아키텍처 결정 문서
```

---

## API 엔드포인트 요약

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/upload` | 문서 업로드 (비동기, document_id 즉시 반환) |
| `GET` | `/api/documents` | 전체 문서 목록 + 처리 상태 |
| `GET` | `/api/documents/{id}/status` | 처리 진행률 폴링 |
| `DELETE` | `/api/documents/{id}` | 문서 및 연관 위키 삭제 |
| `POST` | `/api/chat` | RAG 채팅 (동기) |
| `POST` | `/api/chat/stream` | RAG 채팅 (SSE 스트리밍) |
| `GET` | `/api/chat/history` | 채팅 세션 이력 |
| `GET` | `/api/wiki` | 위키 페이지 목록 (트리 또는 flat) |
| `GET` | `/api/wiki/{id}` | 위키 페이지 조회 |
| `PUT` | `/api/wiki/{id}` | 위키 페이지 편집 |
| `DELETE` | `/api/wiki/{id}` | 위키 페이지 삭제 |
| `POST` | `/api/wiki/{id}/refine` | AI 정제 (기존 내용 개선) |
| `POST` | `/api/wiki/merge` | 다중 페이지 병합 |
| `GET` | `/api/wiki/duplicates` | 유사 페이지 탐지 |
| `GET` | `/api/wiki/{id}/revisions` | 편집 이력 조회 |
| `GET` | `/api/stats` | 시스템 통계 (문서 수, DB 용량 등) |
