"""Pydantic schemas for the LLM layer.

Every provider returns ``WikiPage`` objects from ``extract_wiki_pages``
so the caller can rely on a single, validated shape.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateOptions(BaseModel):
    """Common generation knobs supported by every provider."""

    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=200_000)
    response_format: str | None = Field(
        default=None,
        description="'json' to request strict JSON output (where supported).",
    )


class WikiPage(BaseModel):
    """One unit of structured knowledge extracted from a chunk."""

    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    content: str = Field(min_length=1)
    updates_existing: str | None = Field(
        default=None,
        description="Exact title of an existing wiki page this should update, or null to create new.",
    )
