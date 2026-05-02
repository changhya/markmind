"""Claude provider — Anthropic API backend (skeleton, body wired in PR-B)."""
from __future__ import annotations

import os
from typing import Any, ClassVar

from .base import LLMProvider
from .errors import ProviderUnavailableError
from .schemas import GenerateOptions, WikiPage


class ClaudeProvider(LLMProvider):
    name: ClassVar[str] = "claude"
    default_model: ClassVar[str] = os.environ.get(
        "MARKMIND_CLAUDE_MODEL", "claude-sonnet-4-6"
    )

    def __init__(self, *, model: str | None = None, **config: Any) -> None:
        super().__init__(model=model, **config)
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderUnavailableError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it or pass api_key= when constructing the provider."
            )
        self._api_key = api_key
        self._base_url = config.get("base_url")
        self._timeout = config.get("timeout", 60)

    def generate(self, prompt, *, system=None, options=None):
        raise NotImplementedError(
            "ClaudeProvider.generate — wired in PR-B (see ADR-001 Action Items)."
        )

    def extract_wiki_pages(self, text_chunk, *, source_name, options=None):
        raise NotImplementedError("ClaudeProvider.extract_wiki_pages — wired in PR-B.")
