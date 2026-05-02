# MIGRATION-001: 기존 backend → src/markmind/llm 전환 가이드

**Companion to:** ADR-001 (LLM Provider 추상화)
**Owner:** changhya
**Target branches:** `main` (단일 브랜치 운영 중)

이 문서는 ADR-001을 실제 GitHub 레포 `changhya/markmind`에 단계적으로 반영하기 위한 PR 단위 작업 분해이다. 각 PR은 단독으로 동작 가능해야 하며(=중간 PR 시점에도 앱이 부팅), 사용자가 PR마다 검토 후 다음 단계를 승인하는 마일스톤 진행 원칙을 따른다.

## 현재 vs 목표 구조

```
[현재]                                    [목표]
markmind/                                 markmind/
├── backend/                              ├── backend/
│   ├── main.py                           │   ├── main.py            ← provider 선택 추가
│   ├── ai/                               │   ├── ai/
│   │   ├── llm.py   ◀ ollama 직접 호출   │   │   └── llm.py         ← src/markmind/llm 위임 shim
│   │   └── parser.py                     │   │       (하위 호환 1주기 후 제거)
│   ├── database/chroma.py                │   ├── database/chroma.py
│   ├── watcher.py                        │   └── watcher.py
│   └── lint_wiki.py                      ├── src/                   ← 신규
└── frontend/                             │   └── markmind/
                                          │       └── llm/
                                          │           ├── base.py
                                          │           ├── schemas.py
                                          │           ├── factory.py
                                          │           ├── errors.py
                                          │           ├── claude_provider.py
                                          │           └── ollama_provider.py
                                          ├── tests/                 ← 신규 (PR-E)
                                          │   └── llm/
                                          ├── docs/architecture/     ← 신규 (이 문서 + ADR-001)
                                          ├── .env.example           ← 신규 (PR-D)
                                          ├── pyproject.toml         ← 신규 (PR-A)
                                          └── frontend/
```

## PR 단계

### PR-A · 패키지 골격 + ADR (이번 산출)

**범위**
- `src/markmind/llm/*.py` 6개 파일 (인터페이스 + provider 골격, 본문 NotImplementedError).
- `pyproject.toml` 추가: `[tool.setuptools.packages.find] where=["src"]` + Python 3.10+ 지정.
- `docs/architecture/ADR-001-llm-provider-abstraction.md`, `MIGRATION-001-llm-provider.md`.
- 기존 `backend/`는 **건드리지 않음**(앱 동작 무영향).

**검증**
- `python -c "from markmind.llm import get_provider, ProviderName"` 임포트 성공.
- `pytest`는 아직 없음.

**머지 조건**: 인터페이스 동의 — Appendix A의 시그니처가 6개월 후 후회 없는지 한 번만 더 확인.

---

### PR-B · Provider 본문 구현 + 어댑터

**범위**
- `ClaudeProvider.generate / extract_wiki_pages`: `anthropic` SDK 호출, `response_format='json'` 시 strict JSON, ParseError로 정규화.
- `OllamaProvider.generate / extract_wiki_pages`: 기존 `backend/ai/llm.py`의 ollama 호출 로직을 그대로 이식. JSON 응답이 단일 dict일 때 `[dict]`로 감싸 ParseError 회피.
- `backend/ai/llm.py` → 얇은 shim:

  ```python
  # backend/ai/llm.py (PR-B 후)
  from markmind.llm import get_provider, ProviderName

  def generate_response(prompt: str, model_name: str = "llama3") -> str:
      return get_provider(ProviderName.OLLAMA, model=model_name).generate(prompt)

  def extract_wiki_pages(text_chunk: str, source_name: str, model_name: str = "llama3") -> list[dict]:
      pages = get_provider(ProviderName.OLLAMA, model=model_name).extract_wiki_pages(
          text_chunk, source_name=source_name
      )
      return [p.model_dump() for p in pages]
  ```
- `requirements.txt` → `anthropic>=0.40` 추가.

**검증**
- 기존 `/api/upload`, `/api/chat` 동작 동일 (Ollama 기준 회귀 없음).
- Claude 호출은 `MARKMIND_DEFAULT_LLM=claude ANTHROPIC_API_KEY=... uvicorn ...`로 수동 검증.

**머지 조건**: Ollama 회귀 없음 + Claude 1회 통합 호출 성공.

---

### PR-C · 요청 단위 provider 선택

**범위**
- `main.py`의 Pydantic 요청 모델에 필드 추가:

  ```python
  class ChatRequest(BaseModel):
      query: str
      provider: ProviderName | None = None
      model: str | None = None

  # /api/upload 도 동일하게 Form 필드 또는 multipart 헤더로 추가
  ```
- 핸들러는 `get_provider(req.provider, model=req.model)` 호출 후 `.generate(...)` / `.extract_wiki_pages(...)`.
- `frontend/src/App.tsx`에 provider 셀렉터 (드롭다운: `claude` / `ollama`) 추가. 채팅 요청 페이로드에 `provider` 포함.
- README 업데이트: "Provider 선택" 섹션.

**검증**
- 같은 PDF를 두 provider로 업로드 → 위키 페이지 수·품질 비교를 README에 기록.
- 응답 미스매치 버그 fix(`chunks_count` → `wiki_pages_created`) 동시 적용.

**머지 조건**: 두 provider가 동일 엔드포인트로 라우팅 가능.

---

### PR-D · 환경변수 / 설정 정리

**범위**
- `.env.example` 신규: `ANTHROPIC_API_KEY=`, `MARKMIND_DEFAULT_LLM=ollama`, `MARKMIND_CLAUDE_MODEL=`, `OLLAMA_HOST=`, `MARKMIND_OLLAMA_MODEL=`.
- `python-dotenv` 추가 + `main.py` 진입점에 `load_dotenv()`.
- `README.md`에 `cp .env.example .env` 단계 추가.

**검증**
- 환경변수 미설정 시 ProviderUnavailableError가 사용자에게 명확히 표시.

---

### PR-E · 테스트

**범위**
- `tests/llm/test_factory.py` — provider 라우팅, 알 수 없는 이름 처리.
- `tests/llm/test_schemas.py` — `WikiPage` validation 경계값.
- `tests/llm/test_extract_wiki_pages.py` — `MockProvider`로 dict-단일/list/잘린-JSON 회복 케이스. **현재 코드의 silent-fail 버그가 회귀 방지 케이스로 박힘.**
- GitHub Actions 워크플로(별 ADR 없이): `lint + pytest`.

**머지 조건**: 그린 CI.

---

## 코드 변경 영향 요약 (callers)

| 위치 | 현재 | PR-B 후 | PR-C 후 |
|---|---|---|---|
| `main.py` `/api/chat` | `generate_response(prompt, request.model)` | 동일 (shim) | `get_provider(req.provider).generate(prompt)` |
| `main.py` `/api/upload` | `extract_wiki_pages(chunk, file.filename)` | 동일 (shim) | `get_provider(req.provider).extract_wiki_pages(chunk, source_name=file.filename)` |
| `watcher.py` | `requests.post(API_URL, ...)` | 동일 | provider 파라미터 전달 옵션(필요시) |
| `lint_wiki.py` | LLM 미사용 | 영향 없음 | 영향 없음 |
| `frontend/App.tsx` | `axios.post('/api/chat', { query })` | 동일 | `{ query, provider }` |

## 롤백 전략

각 PR은 revert 가능. 특히 PR-B 머지 후 Claude 호출에서 회귀가 발견되면:
1. `MARKMIND_DEFAULT_LLM=ollama`로 환경변수만 변경 → Claude 라우트 차단.
2. `requirements.txt`의 `anthropic` 라인은 유지(임포트는 lazy라 부팅에 무해).
3. `main.py`의 provider 필드는 무시되고 기본값으로 동작.

추상화 자체를 되돌리는 큰 롤백은 PR-A를 revert하면 됨. 기존 `backend/ai/llm.py`는 PR-B 시점에 shim으로 바뀌지만 시그니처는 동일하므로 caller 변경 불필요.

## 비-목표 (이번 추상화에 포함하지 않는 것)

- 스트리밍 응답 (`generate_stream`).
- Tool use / agentic 합성 (별도 ADR-003 후보).
- 응답 캐시.
- 임베딩 provider 추상화 → ADR-002 (검색·BM25)에서 다룸.
- 멀티테넌시 / workspace_id → 스토리지 ADR (별도).
