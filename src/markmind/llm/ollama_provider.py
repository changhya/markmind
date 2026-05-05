"""Ollama provider — local inference via the Ollama daemon.

Accepted constructor config:
    host    — Ollama base URL (default env OLLAMA_HOST or http://127.0.0.1:11434).
    timeout — seconds, default 120 (local generation can be slow).
"""
from __future__ import annotations

import os
from typing import Any, ClassVar

from ._parsing import parse_wiki_pages_json
from .base import LLMProvider
from .errors import ParseError, ProviderUnavailableError
from .schemas import GenerateOptions, WikiPage

_EXTRACT_PROMPT_TEMPLATE = """\
You are a knowledge curator maintaining a wiki knowledge base.
Your job is to integrate new content into the existing wiki — not just extract facts, \
but connect them to what is already known.

EXISTING WIKI PAGES:
{existing_context}

SOURCE: {source_name}

NEW CONTENT TO INTEGRATE:
{text_chunk}

Instructions:
1. Extract 1-3 key concepts, entities, or topics from the new content.
2. For each concept:
   - If it clearly overlaps with an EXISTING wiki page, set "updates_existing" to \
that page's EXACT title. The content you write should enrich and extend the existing page.
   - Otherwise set "updates_existing" to null to create a new page.
3. In the "content" field, use [[Page Title]] syntax to cross-reference related pages \
(both existing and new ones from this response).
4. Write content in Markdown. Be concise but comprehensive.

Return ONLY a valid JSON array. No prose, no code fences:
[
  {{
    "title": "Concept Name",
    "summary": "One sentence describing this concept.",
    "tags": ["tag1", "tag2"],
    "content": "Markdown content with [[cross-references]] to related pages...",
    "updates_existing": null
  }}
]"""


class OllamaProvider(LLMProvider):
    name: ClassVar[str] = "ollama"
    default_model: ClassVar[str] = os.environ.get(
        "MARKMIND_OLLAMA_MODEL", "llama3.2:1b"
    )

    def __init__(self, *, model: str | None = None, **config: Any) -> None:
        super().__init__(model=model, **config)
        self._host = config.get("host") or os.environ.get(
            "OLLAMA_HOST", "http://127.0.0.1:11434"
        )
        self._timeout = config.get("timeout", 600)  # CPU 추론은 청크당 수 분 소요
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            try:
                from ollama import Client  # type: ignore
            except ImportError as exc:
                raise ProviderUnavailableError(
                    "The 'ollama' package is not installed. "
                    "Run: pip install ollama"
                ) from exc
            self._client = Client(host=self._host, timeout=self._timeout)
        return self._client

    @staticmethod
    def _normalize_sdk_error(exc: Exception) -> ProviderUnavailableError:
        return ProviderUnavailableError(
            f"Ollama call failed (is the daemon running?): {exc}"
        )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        options: GenerateOptions | None = None,
    ) -> str:
        opts = options or GenerateOptions()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        try:
            response = client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": opts.temperature,
                    "num_predict": opts.max_tokens,
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise self._normalize_sdk_error(exc) from exc

        try:
            return response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderUnavailableError(
                f"Unexpected Ollama response shape: {response!r}"
            ) from exc

    def extract_wiki_pages(
        self,
        text_chunk: str,
        *,
        source_name: str,
        existing_context: str = "",
        options: GenerateOptions | None = None,
    ) -> list[WikiPage]:
        opts = options or GenerateOptions(temperature=0.1, max_tokens=4096)
        ctx = existing_context or "None yet (this is the first ingest)"
        prompt = _EXTRACT_PROMPT_TEMPLATE.format(
            existing_context=ctx,
            source_name=source_name,
            text_chunk=text_chunk,
        )

        client = self._get_client()
        try:
            response = client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={
                    "temperature": opts.temperature,
                    "num_predict": opts.max_tokens,
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise self._normalize_sdk_error(exc) from exc

        try:
            raw = response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ParseError(
                f"Unexpected Ollama response shape: {response!r}"
            ) from exc

        return parse_wiki_pages_json(raw)
