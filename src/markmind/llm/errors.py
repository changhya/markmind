"""Domain-level exceptions for the LLM layer.

Provider implementations MUST translate SDK-specific exceptions
(anthropic.APIError, ollama.ResponseError, ...) into one of these
classes so callers never need to import vendor SDKs.
"""


class LLMError(Exception):
    """Base class for all LLM provider errors."""


class ProviderUnavailableError(LLMError):
    """Raised when a provider cannot be reached or is misconfigured."""


class ParseError(LLMError):
    """Raised when the model returned content that violates the expected schema."""
