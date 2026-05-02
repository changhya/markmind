"""Ollama provider — local inference (skeleton, body wired in PR-B)."""
from __future__ import annotations

import os
from typing import Any, ClassVar

from .base import LLMProvider
from .schemas import GenerateOptions, WikiPage


class OllamaProvider(LLMProvider):
    name: ClassVar[str] = "ollama"
    default_model: ClassVar[str] = os.environ.get("MARKMIND_OLLAMA_MODEL", "llama3")

    def __init__(self, *, model: str | None = None, **config: Any) -> None:
        super().__init__(model=model, **config)
        self._host = config.get("host") or os.environ.get(
            "OLLAMA_HOST", "http://127.0.0.1:11434"
        )
        self._timeout = config.get("timeout", 120)

    def generate(self, prompt, *, system=None, options=None):
        raise NotImplementedError(
            "OllamaProvider.generate — wired in PR-B (delegate from backend/ai/llm.py)."
        )

    def extract_wiki_pages(self, text_chunk, *, source_name, options=None):
        raise NotImplementedError("OllamaProvider.extract_wiki_pages — wired in PR-B.")
