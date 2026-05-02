"""Claude provider — Anthropic API backend.

Accepted constructor config:
    api_key  — defaults to env ANTHROPIC_API_KEY.
    base_url — optional override.
    timeout  — request timeout in seconds (default 60).
    max_retries — Anthropic SDK level retries (default 2).

The ``anthropic`` package is imported lazily inside methods so that
environments without it can still import this module (e.g. CI running
Ollama-only tests).
"""
from __future__ import annotations

import json
import os
from typing import Any, ClassVar

from ._parsing import parse_wiki_pages_json
from .base import LLMProvider
from .errors import ParseError, ProviderUnavailableError
from .schemas import GenerateOptions, WikiPage

_EXTRACT_SYSTEM_PROMPT = (
    "You are an expert knowledge extractor for a wiki. "
    "Read the supplied source text and return a JSON ARRAY of distinct "
    "knowledge pages. Each page MUST have keys: title (1 short sentence), "
    "summary (1 sentence), tags (list of strings), content (Markdown body). "
    "Return ONLY the JSON array — no prose, no code fences."
)


def _user_prompt_for_extraction(text_chunk: str, source_name: str) -> str:
    return (
        f"Source name: {source_name}\n\n"
        f"Source text:\n{text_chunk}\n\n"
        "Return the JSON array now."
    )


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
                "Export it or pass api_key= when constructing ClaudeProvider."
            )
        self._api_key = api_key
        self._base_url = config.get("base_url") or os.environ.get("ANTHROPIC_BASE_URL")
        self._timeout = config.get("timeout", 60)
        self._max_retries = config.get("max_retries", 2)
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic  # type: ignore
            except ImportError as exc:
                raise ProviderUnavailableError(
                    "The 'anthropic' package is not installed. "
                    "Run: pip install anthropic>=0.40"
                ) from exc

            kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "timeout": self._timeout,
                "max_retries": self._max_retries,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = Anthropic(**kwargs)
        return self._client

    @staticmethod
    def _normalize_sdk_error(exc: Exception) -> ProviderUnavailableError:
        return ProviderUnavailableError(f"Claude API call failed: {exc}")

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerateOptions | None = None,
    ) -> str:
        opts = options or GenerateOptions()
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=opts.max_tokens,
                temperature=opts.temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001
            raise self._normalize_sdk_error(exc) from exc

        parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()

    def extract_wiki_pages(
        self,
        text_chunk: str,
        *,
        source_name: str,
        options: GenerateOptions | None = None,
    ) -> list[WikiPage]:
        opts = options or GenerateOptions(temperature=0.1, max_tokens=4096)
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=opts.max_tokens,
                temperature=opts.temperature,
                system=_EXTRACT_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": _user_prompt_for_extraction(text_chunk, source_name),
                }],
            )
        except Exception as exc:  # noqa: BLE001
            raise self._normalize_sdk_error(exc) from exc

        raw = "".join(
            getattr(b, "text", "") or "" for b in getattr(response, "content", []) or []
        )
        try:
            return parse_wiki_pages_json(raw)
        except ParseError:
            raise
        except json.JSONDecodeError as exc:
            raise ParseError(f"Claude returned non-JSON: {exc.msg}") from exc
