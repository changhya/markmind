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
You are an expert knowledge extractor. Analyze the following text and extract \
key entities, concepts, or topics to create Wiki pages.
For each key topic, provide a Title, a one-sentence Summary, a list of Tags, \
and the detailed Content (in Markdown format).

Source Name: {source_name}

Text:
{text_chunk}

Output strictly in JSON format as a list of objects. Do not include any other \
text or markdown formatting like ```json.
Example format:
[
  {{
    "title": "Topic Name",
    "summary": "A short one-sentence summary.",
    "tags": ["tag1", "tag2"],
    "content": "Detailed markdown content..."
  }}
]
"""


class OllamaProvider(LLMProvider):
    name: ClassVar[str] = "ollama"
    default_model: ClassVar[str] = os.environ.get(
        "MARKMIND_OLLAMA_MODEL", "llama3"
    )

    def __init__(self, *, model: str | None = None, **config: Any) -> None:
        super().__init__(model=model, **config)
        self._host = config.get("host") or os.environ.get(
            "OLLAMA_HOST", "http://127.0.0.1:11434"
        )
        self._timeout = config.get("timeout", 120)
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
        options: GenerateOptions | None = None,
    ) -> list[WikiPage]:
        opts = options or GenerateOptions(temperature=0.1, max_tokens=4096)
        prompt = _EXTRACT_PROMPT_TEMPLATE.format(
            source_name=source_name, text_chunk=text_chunk
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
