"""Internal JSON parsing helpers shared by all providers.

Both Claude and Ollama can return wiki-page JSON in inconsistent shapes:
    - well-formed list:        [{"title": ...}, ...]
    - single object:           {"title": ...}            (must wrap in list)
    - object with "pages" key: {"pages": [...]}          (common Claude habit)
    - markdown-fenced:         ```json\n[...]\n```
    - prefix/suffix prose:     "Sure, here you go:\n[...]"
    - truncated / invalid:     "[ { \"title\":"          (raise ParseError)

This module normalizes those shapes into ``list[WikiPage]`` and raises
``ParseError`` only on truly broken responses — never silently returning
``[]`` for parser failures (which was a real bug in the legacy code).
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .errors import ParseError
from .schemas import WikiPage

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_FIRST_JSON_RE = re.compile(r"(\[.*\]|\{.*\})", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if present, otherwise return text unchanged."""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _isolate_json(text: str) -> str:
    """Pull out the largest leading JSON-looking substring."""
    text = _strip_fences(text)
    if text.startswith(("[", "{")):
        return text
    m = _FIRST_JSON_RE.search(text)
    if m:
        return m.group(1)
    return text


def _normalize_to_list(payload: Any) -> list[dict]:
    """Coerce supported JSON shapes into a list of dict pages."""
    if isinstance(payload, list):
        if all(isinstance(x, dict) for x in payload):
            return payload
        raise ParseError("JSON list contains non-object entries.")

    if isinstance(payload, dict):
        for key in ("pages", "wiki_pages", "items", "data", "results"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return _normalize_to_list(inner)
        if any(k in payload for k in ("title", "content")):
            return [payload]
        raise ParseError(
            f"JSON object lacks expected keys; got keys={list(payload)[:5]}."
        )

    raise ParseError(f"Unsupported JSON root type: {type(payload).__name__}.")


def parse_wiki_pages_json(raw: str) -> list[WikiPage]:
    """Parse a model's wiki-pages response into validated ``WikiPage`` objects.

    Raises
    ------
    ParseError
        Empty response, invalid JSON, or no salvageable pages.
    """
    if not raw or not raw.strip():
        raise ParseError("Empty model response.")

    candidate = _isolate_json(raw)

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        snippet = candidate[:200].replace("\n", " ")
        raise ParseError(f"Invalid JSON: {exc.msg} | snippet={snippet!r}") from exc

    pages_raw = _normalize_to_list(payload)

    pages: list[WikiPage] = []
    skipped: list[str] = []
    for i, item in enumerate(pages_raw):
        try:
            pages.append(WikiPage.model_validate(item))
        except ValidationError as exc:
            skipped.append(f"#{i}: {exc.errors()[0].get('msg', 'invalid')}")
            continue

    if not pages:
        raise ParseError(
            f"All {len(pages_raw)} returned pages failed validation: "
            f"{'; '.join(skipped[:3])}"
        )
    return pages
