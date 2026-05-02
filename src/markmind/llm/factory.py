"""Provider factory."""
from __future__ import annotations

import os
from enum import Enum
from typing import Any

from .base import LLMProvider
from .errors import ProviderUnavailableError


class ProviderName(str, Enum):
    """Supported LLM backends."""

    CLAUDE = "claude"
    OLLAMA = "ollama"


def _build_claude(**config: Any) -> LLMProvider:
    from .claude_provider import ClaudeProvider
    return ClaudeProvider(**config)


def _build_ollama(**config: Any) -> LLMProvider:
    from .ollama_provider import OllamaProvider
    return OllamaProvider(**config)


_REGISTRY: dict[ProviderName, Any] = {
    ProviderName.CLAUDE: _build_claude,
    ProviderName.OLLAMA: _build_ollama,
}


def get_provider(
    name: ProviderName | str | None = None,
    /,
    **config: Any,
) -> LLMProvider:
    """Return a configured ``LLMProvider`` instance."""
    chosen = name or os.environ.get("MARKMIND_DEFAULT_LLM") or ProviderName.OLLAMA
    try:
        chosen = ProviderName(chosen)
    except ValueError as exc:
        valid = ", ".join(p.value for p in ProviderName)
        raise ProviderUnavailableError(
            f"Unknown LLM provider {chosen!r}. Valid: {valid}."
        ) from exc
    return _REGISTRY[chosen](**config)
