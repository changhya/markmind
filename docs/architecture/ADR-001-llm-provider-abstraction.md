# ADR-001: LLM Provider 추상화 (Claude + Ollama 듀얼)

**Status:** Proposed
**Date:** 2026-05-03
**Deciders:** changhya (오너 / 단독 결정)
**Supersedes:** —
**Related:** `backend/ai/llm.py`(현재 구현), `markmind_b2b_planning.html`(M1~M3 마일스톤)

## Context

### 현재 상태
GitHub 레포 `changhya/markmind`의 LLM 호출 코드는 `backend/ai/llm.py` 한 파일에 집약돼 있다. `ollama` 라이브러리를 직접 import하고 두 함수를 노출한다.

```python
# backend/ai/llm.py (현재)
import ollama

def generate_response(prompt: str, model_name: str = "llama3") -> str: ...
def extract_wiki_pages(text_chunk: str, source_name: str, model_name: str = "llama3") -> list[dict]: ...
```

`main.py`의 `/api/upload`, `/api/chat`이 이 두 함수를 직접 호출한다.

### 원하는 상태
기획안(B2B SaaS)에서 본진 LLM은 **Claude API**(Karpathy식 위키 합성 품질 확보용)이지만, 초기 시연·민감데이터 고객·오프라인 데모 시나리오에서 **Ollama 로컬 추론**도 계속 필요하다. 따라서 다음 두 모드가 병존해야 한다.

1. **Cloud / Production** — Claude API (`claude-sonnet-4-6`, `claude-opus-4-6`)
2. **Local Edge / Demo** — Ollama (`llama3`, `qwen2`, …)

오너 결정(2026-05-03): 두 provider를 동시 지원하고, 사용자가 **요청 단위로** 선택한다. 환경변수로 기본값 지정.

### 동인 / 제약
- **품질 격차**: Claude는 한국어·구조화 추출 품질이 명확히 우수. 위키 합성(extract_wiki_pages)에서 격차가 가장 큼.
- **비용**: Claude는 토큰당 과금. 대량 인덱싱 시 비용 폭주 가능. → 비용 인지 라우팅이 필요.
- **민감 데이터**: 제약·바이오 고객 일부는 외부 API 송신을 거부할 수 있음. → 로컬 모드가 SKU의 일부.
- **테스트 용이성**: 외부 호출에 매번 의존하면 단위 테스트가 불가. → Mock 가능한 인터페이스 필요.
- **확장성**: 6~12개월 내 OpenAI / Gemini / 사내 모델 추가 가능성 ≥ 50%. → 추상 layer가 미래 비용을 줄임.
- **개발 시간**: 1~2일 분량으로 끝내야 한다(스코프 결정 결과 = "LLM 레이어만").

### 비기능 요구
- 단일 요청 latency: Claude 1~5s, Ollama 5~15s (모델별 변동). 사용자 측에서 알고 선택.
- Provider 교체로 인한 main.py 코드 변경 없음(엔드포인트는 provider-agnostic).
- 새 provider 추가 비용: 단일 파일(`*_provider.py`) 추가 + factory에 1줄 등록.

## Decision

`src/markmind/llm/` 패키지에 **추상 클래스 기반의 Provider 인터페이스**를 도입한다.

```
src/markmind/llm/
├── __init__.py            # 공개 API (LLMProvider, ProviderName, get_provider)
├── base.py                # LLMProvider 추상 클래스
├── schemas.py             # Pydantic: WikiPage, GenerateOptions
├── claude_provider.py     # ClaudeProvider (anthropic SDK)
├── ollama_provider.py     # OllamaProvider (ollama lib)
├── factory.py             # ProviderName enum + get_provider()
└── errors.py              # LLMError, ProviderUnavailableError, ParseError
```

### 인터페이스(요약)

```python
class LLMProvider(ABC):
    name: ClassVar[str]

    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None,
                 options: GenerateOptions | None = None) -> str: ...

    @abstractmethod
    def extract_wiki_pages(self, text_chunk: str, *, source_name: str,
                           options: GenerateOptions | None = None) -> list[WikiPage]: ...

    def health_check(self) -> bool: ...   # 기본 구현: generate("ping") 짧게
```

### 요청 단위 선택
FastAPI 요청 모델에 `provider` 필드 추가.

```python
class ChatRequest(BaseModel):
    query: str
    provider: ProviderName | None = None   # None → 기본값(env)
    model: str | None = None               # None → provider별 기본 모델
```

`provider` 미지정 시 환경변수 `MARKMIND_DEFAULT_LLM`(기본 `ollama`) 사용. 핸들러는 `get_provider(name)`로 인스턴스를 받아 호출.

### 핵심 원칙
1. **인터페이스는 좁게**: `generate`와 `extract_wiki_pages`만. 그 이상은 callers의 책임.
2. **외부 SDK는 provider 내부로 격리**: `anthropic`, `ollama` 모듈 import는 각각 그 파일 내부에서만 발생. 다른 코드는 `LLMProvider` 인터페이스만 안다.
3. **에러는 도메인 타입으로 정규화**: 네트워크/속도 제한/JSON 파싱 실패 모두 `LLMError` 계층으로 변환. caller는 SDK별 예외를 알 필요 없음.
4. **Pydantic 스키마로 응답 검증**: 깨진 JSON·dict 단일 객체 응답을 silently 흘리지 않음(현재 코드의 버그 #4 해소).

## Options Considered

### Option A: if/else 분기 그대로 + ollama 옆에 anthropic 추가

| 차원 | 평가 |
|---|---|
| 복잡도 | 낮음 |
| 비용 | 거의 0 (1~2시간) |
| 확장성 | 낮음 — provider 추가마다 분기 폭증 |
| 테스트 용이성 | 낮음 — 모킹이 어려움(모듈 직접 import) |
| 미래 부담 | 높음 — 3번째 provider 시점에 결국 리팩토링 |

**Pros:** 즉시 Claude 동작 가능. 학습 비용 0.
**Cons:** 1~2달 안에 Gemini/OpenAI 추가 시 동일 결정을 다시 해야 함. 단위 테스트가 사실상 불가.

### Option B: ABC 기반 Provider 추상화 (선택)

| 차원 | 평가 |
|---|---|
| 복잡도 | 중간 |
| 비용 | 1~2일 (스코프 합의 일치) |
| 확장성 | 높음 — 새 provider = 단일 파일 |
| 테스트 용이성 | 높음 — `MockProvider`로 endpoint 테스트 |
| 미래 부담 | 낮음 |

**Pros:** Python 표준 패턴. 외부 의존성 0(`abc`만 사용). 코드 리뷰 진입장벽 낮음. Provider별 재시도/캐시/사용량 로깅을 데코레이터로 일관 적용 가능.
**Cons:** 인터페이스 한 개 더. 잘못 정의하면 1년 후 부담(LLM 도메인은 빠르게 변함 — tool use, 스트리밍, multimodal 등을 인터페이스에 어떻게 들이느냐가 미래 화두).

### Option C: LangChain / LlamaIndex 같은 외부 추상화 도입

| 차원 | 평가 |
|---|---|
| 복잡도 | 높음 |
| 비용 | 2~3일 + 학습 |
| 확장성 | 매우 높음 — 수십 개 provider 즉시 |
| 테스트 용이성 | 중간 — 추상화가 두꺼워 디버깅 비용↑ |
| 미래 부담 | 중간 — breaking change 빈도 높음(0.x ↔ 0.y) |

**Pros:** 50+ provider, 내장 retriever / chain. M2 이후 RAG가 복잡해지면 매력 큼.
**Cons:** **"LLM 레이어만"** 스코프 합의를 깬다. 의존성 무게(수백 MB), 추상화 누수(LangChain 자체 객체가 코드 전체에 퍼짐), 한국어/구조화 추출에서 추가 가치는 한정적. **현 시점에 시기상조.**

### Option D: 함수형 dispatcher (`PROVIDERS = {"claude": fn, "ollama": fn}`)

| 차원 | 평가 |
|---|---|
| 복잡도 | 낮음 |
| 비용 | 1일 |
| 확장성 | 중간 |
| 테스트 용이성 | 중간 |
| 미래 부담 | 중간 — provider별 상태(클라이언트 인스턴스, 토큰 카운터)가 늘어나면 객체로 옮겨야 함 |

**Pros:** Python 답고 가벼움. Side-effect 적음.
**Cons:** Provider별 클라이언트 lifecycle(connection pool, auth 갱신) 관리 시 모듈 전역 상태가 늘어남. M2 단계에서 결국 클래스로 회귀할 가능성 큼.

## Trade-off Analysis

핵심 축은 **"지금의 단순함" vs "M2~M3에서 후회 비용"**. 1차 타깃(M2 = Seegene 파일럿, 6주 후)에서는:
- Claude 본진 + Ollama 폴백이 거의 확정 → **Provider ≥ 2개**.
- 도메인 프롬프트 / 모델 라우팅 / 비용 추적 같은 cross-cutting 요구가 등장 → **공통 진입점이 있어야 데코레이터로 적용 가능**.
- 단위 테스트가 없으면 LLM 응답 변동에 취약 → **Mock 가능한 인터페이스가 사실상 필수**.

이 세 가지가 모두 **Option B**의 가치 명제와 일치한다. Option A/D는 1~2달 안에 다시 만지게 될 가능성이 높고, Option C는 현 시점 스코프(LLM 레이어만, 1~2일)와 맞지 않는다.

따라서 **Option B 채택**.

## Consequences

### 쉬워지는 것
- **새 provider 추가**: 단일 파일 + factory 1줄. Gemini/OpenAI 등 도입 비용이 시간 단위.
- **단위 테스트**: `MockProvider`로 `/api/upload`·`/api/chat` 통합 테스트 가능. CI에 LLM 호출 없이 회귀 검증.
- **Cross-cutting 정책**: 재시도(`tenacity`), 토큰 사용량 로깅, 요금 한도 차단을 base 클래스 데코레이터에 한 번만 구현.
- **요청별 선택**: SaaS 사용자가 프로젝트별 provider 지정 가능. M2 파일럿에서 "이 워크스페이스는 무조건 로컬"같은 정책 도입이 쉬워짐.

### 어려워지는 것
- **레이어 1개 추가**: 새 컨트리뷰터가 LLM 호출을 따라가려면 인터페이스 → factory → provider 순으로 이동.
- **인터페이스 변경 비용**: 두 provider가 모두 구현해야 함. 스트리밍·tool use를 인터페이스에 들일 때 큰 결정이 됨(향후 ADR-002로 다룸).
- **설정 관리**: 환경변수가 늘어남(`ANTHROPIC_API_KEY`, `OLLAMA_HOST`, `MARKMIND_DEFAULT_LLM`). `.env.example` 동기화 책임 발생.

### 재고할 것
- **스트리밍 응답**(현재 인터페이스 미포함): 채팅 UX 개선 시점에 `generate_stream()` 추가 여부 결정.
- **Tool use / 에이전트 합성**: M2 이후 Karpathy식 합성을 강화할 때 별도 인터페이스(`run_agent`)로 추가할지 검토. 현재는 `extract_wiki_pages`로 충분.
- **응답 캐시**: 동일 청크 재처리 방지용 fingerprint 기반 캐시. M1 후반 또는 M2 초반에 별도 ADR.
- **임베딩 provider**: 본 ADR 범위 외(검색 ADR-002에서 다룸). 단, 임베딩도 동일 패턴(`EmbeddingProvider`)을 따른다는 점을 본 ADR이 선례로 남김.

## Action Items

1. [ ] **PR-A** `src/markmind/llm/` 패키지 골격 추가 (base/schemas/factory/errors + Claude·Ollama provider 골격, 본문은 NotImplementedError 또는 기존 동작 유지). 본 ADR과 함께 산출.
2. [ ] **PR-B** `backend/ai/llm.py`를 신규 패키지에 위임하는 얇은 어댑터로 교체. 외부에서 import하던 `generate_response`, `extract_wiki_pages` 시그니처는 그대로 유지(하위호환 1주기).
3. [ ] **PR-C** `main.py`의 `ChatRequest` / `UploadRequest`에 `provider`, `model` 필드 추가. 기본값은 `MARKMIND_DEFAULT_LLM` 환경변수.
4. [ ] **PR-D** `requirements.txt`에 `anthropic>=0.40` 추가, `.env.example` 신규 작성(키 항목만).
5. [ ] **PR-E** `tests/llm/` 추가 — `MockProvider`, JSON 파싱 회복(현재 코드 버그 #4 회귀 방지), provider 라우팅 테스트.
6. [ ] **Docs** `README.md`에 "Provider 선택" 섹션 추가, `docs/architecture/MIGRATION-001-llm-provider.md`로 PR 단계 문서화(본 ADR과 동시 산출).
7. [ ] **Follow-up ADR-002**: 검색·임베딩 layer(BM25 + 한국어 임베딩) 추상화 — 본 ADR 승인 후 별도 작성.

---

## Appendix A — 인터페이스 시그니처 초안

```python
# src/markmind/llm/base.py
from abc import ABC, abstractmethod
from typing import ClassVar
from .schemas import WikiPage, GenerateOptions

class LLMProvider(ABC):
    name: ClassVar[str]
    default_model: ClassVar[str]

    def __init__(self, *, model: str | None = None, **config) -> None: ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerateOptions | None = None,
    ) -> str: ...

    @abstractmethod
    def extract_wiki_pages(
        self,
        text_chunk: str,
        *,
        source_name: str,
        options: GenerateOptions | None = None,
    ) -> list[WikiPage]: ...

    def health_check(self) -> bool: ...
```

```python
# src/markmind/llm/factory.py
from enum import Enum
from .base import LLMProvider

class ProviderName(str, Enum):           # Py3.10 호환 (StrEnum은 3.11+)
    CLAUDE = "claude"
    OLLAMA = "ollama"

def get_provider(name: ProviderName | str | None = None, **config) -> LLMProvider:
    """환경변수 fallback과 lazy 초기화 포함."""
```

## Appendix B — 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MARKMIND_DEFAULT_LLM` | `ollama` | provider 미지정 요청의 기본값 |
| `ANTHROPIC_API_KEY` | — | Claude provider 활성화 조건 |
| `MARKMIND_CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude 기본 모델 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 엔드포인트 |
| `MARKMIND_OLLAMA_MODEL` | `llama3` | Ollama 기본 모델 |
