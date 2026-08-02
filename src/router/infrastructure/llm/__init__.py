"""LLM Infrastructure Package.

Exports the core LLM provider and resilience components:
- ClaudeProvider: Anthropic API wrapper.
- OpenAIProvider: OpenAI API wrapper.
- RetryManager: Exponential backoff with full jitter.
- OutputParser: Multi-stage self-healing JSON parser.
- JSONValidator: Pydantic schema validation & anti-hallucination check.
"""

from router.infrastructure.llm.claude_provider import ClaudeProvider, ClaudeProviderError
from router.infrastructure.llm.json_validator import JSONValidator, RoutingAction, ValidationResult
from router.infrastructure.llm.openai_provider import OpenAIProvider, OpenAIProviderError
from router.infrastructure.llm.output_parser import OutputParser, ParseResult
from router.infrastructure.llm.retry_manager import (
    MaxRetriesExceededError,
    RetryAttempt,
    RetryManager,
    RetryResult,
)

__all__ = [
    "ClaudeProvider",
    "ClaudeProviderError",
    "OpenAIProvider",
    "OpenAIProviderError",
    "RetryManager",
    "RetryAttempt",
    "RetryResult",
    "MaxRetriesExceededError",
    "OutputParser",
    "ParseResult",
    "JSONValidator",
    "RoutingAction",
    "ValidationResult",
]
