"""LLMProvider — abstract base for every LLM backend.

Design rules (see ADR-001):
- Providers expose ONLY ``generate`` and ``extract_wiki_pages``.
- All vendor SDK imports stay inside the concrete provider file.
- Vendor exceptions are translated into ``markmind.llm.errors.*``.
- Responses returned to callers are validated Pydantic objects, never raw dicts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from .schemas import GenerateOptions, WikiPage


class LLMProvider(ABC):
    """Abstract LLM provider."""

    name: ClassVar[str]
    default_model: ClassVar[str]

    def __init__(self, *, model: str | None = None, **config: Any) -> None:
        self.model = model or self.default_model
        self._config = config

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
        existing_context: str = "",
        options: GenerateOptions | None = None,
    ) -> list[WikiPage]: ...

    def health_check(self) -> bool:
        try:
            self.generate(
                "ping",
                options=GenerateOptions(max_tokens=4, temperature=0.0),
            )
        except Exception:  # noqa: BLE001
            return False
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} model={self.model!r}>"
