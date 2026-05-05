"""Legacy LLM facade — delegates to the new ``markmind.llm`` package.

Kept as a thin shim for ONE deprecation cycle so that the existing
``main.py`` callers (``generate_response`` / ``extract_wiki_pages``) keep
working unchanged. New code should import from ``markmind.llm`` directly.

See:
    docs/architecture/ADR-001-llm-provider-abstraction.md
    docs/architecture/MIGRATION-001-llm-provider.md (PR-B)
"""
from __future__ import annotations

import warnings
from typing import Any

from markmind.llm import ProviderName, get_provider
from markmind.llm.errors import ParseError, ProviderUnavailableError

# Backward-compat default: the legacy code targeted Ollama (llama3).
_LEGACY_PROVIDER = ProviderName.OLLAMA


def generate_response(prompt: str, model_name: str = "llama3") -> str:
    """Deprecated: use ``markmind.llm.get_provider(...).generate(...)``."""
    warnings.warn(
        "backend.ai.llm.generate_response is deprecated; "
        "use markmind.llm.get_provider().generate() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        provider = get_provider(_LEGACY_PROVIDER, model=model_name)
        return provider.generate(prompt)
    except ProviderUnavailableError as exc:
        return (
            f"Ollama Error: {exc}\n"
            f"Make sure Ollama is running locally and the '{model_name}' model is pulled."
        )


def extract_wiki_pages(
    text_chunk: str,
    source_name: str,
    model_name: str = "llama3",
    existing_context: str = "",
) -> list[dict[str, Any]]:
    """Deprecated: use ``markmind.llm.get_provider(...).extract_wiki_pages(...)``."""
    warnings.warn(
        "backend.ai.llm.extract_wiki_pages is deprecated; "
        "use markmind.llm.get_provider().extract_wiki_pages() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        provider = get_provider(_LEGACY_PROVIDER, model=model_name)
        pages = provider.extract_wiki_pages(
            text_chunk, source_name=source_name, existing_context=existing_context
        )
        return [p.model_dump() for p in pages]
    except (ProviderUnavailableError, ParseError) as exc:
        print(f"[LLM] Extraction error: {exc}", flush=True)
        return []
