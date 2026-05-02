"""LLM Provider abstraction.

Public API:
    LLMProvider               — abstract base class.
    ProviderName              — enum of supported providers.
    GenerateOptions, WikiPage — request / response schemas.
    get_provider              — factory.
    LLMError, ParseError, ProviderUnavailableError — domain exceptions.

See docs/architecture/ADR-001-llm-provider-abstraction.md for the design rationale.
"""
from .base import LLMProvider
from .errors import LLMError, ParseError, ProviderUnavailableError
from .factory import ProviderName, get_provider
from .schemas import GenerateOptions, WikiPage

__all__ = [
    "LLMProvider",
    "ProviderName",
    "get_provider",
    "GenerateOptions",
    "WikiPage",
    "LLMError",
    "ParseError",
    "ProviderUnavailableError",
]
