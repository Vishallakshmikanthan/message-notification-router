"""OpenAI Provider — OpenAI GPT API wrapper with retry and output parsing.

Provides a production-ready integration with the OpenAI GPT API,
implementing the ILLMInterface contract from decision_ports.py.

Features:
- Structured prompt dispatch via PromptBuilder.
- Automatic prompt caching support.
- Exponential backoff retry via RetryManager.
- 4-stage output parsing via OutputParser.
- JSON schema validation via JSONValidator.
- Zero hardcoded API keys (reads from env/settings).

Spec: llm_strategy.md §2 (Tier 1: Fast Single-Pass Router).
      deployment.md §3 (Secrets & API Key Governance).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from router.application.prompts.prompt_builder import BuiltPrompt
from router.infrastructure.llm.output_parser import OutputParser, ParseResult
from router.infrastructure.llm.retry_manager import MaxRetriesExceededError, RetryManager

logger = logging.getLogger(__name__)

# Model identifiers
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_OPENAI_DEEP_MODEL = "gpt-4o"

# API call timeout (seconds)
_DEFAULT_TIMEOUT_SECS = 10.0


class OpenAIProviderError(Exception):
    """Raised when the OpenAI API call fails after all retries."""


class OpenAIProvider:
    """OpenAI GPT API provider with retry and output parsing.

    Wraps the OpenAI Python SDK with production resilience features:
    - Retry logic with exponential backoff (max 3 attempts).
    - Multi-stage JSON repair pipeline.

    Args:
        api_key: OpenAI API key. Reads from OPENAI_API_KEY env if None.
        model: OpenAI model identifier (default: gpt-4o-mini).
        retry_manager: Optional custom RetryManager (uses default if None).
        output_parser: Optional custom OutputParser (uses default if None).
        timeout_secs: API call timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_OPENAI_MODEL,
        retry_manager: RetryManager | None = None,
        output_parser: OutputParser | None = None,
        timeout_secs: float = _DEFAULT_TIMEOUT_SECS,
    ) -> None:
        """Initialize OpenAIProvider.

        Args:
            api_key: OpenAI API key.
            model: Model identifier string.
            retry_manager: Retry manager instance.
            output_parser: Output parser instance.
            timeout_secs: Request timeout.
        """
        self._api_key = api_key or self._read_api_key()
        self._model = model
        self._retry_manager = retry_manager or RetryManager()
        self._output_parser = output_parser or OutputParser()
        self._timeout_secs = timeout_secs
        self._client = self._init_client()
        logger.info(
            "OpenAIProvider initialized",
            extra={"model": model, "client_available": self._client is not None},
        )

    def complete(self, prompt: BuiltPrompt) -> dict[str, Any]:
        """Send a prompt to OpenAI and return the parsed JSON response.

        Args:
            prompt: BuiltPrompt assembled by PromptBuilder.

        Returns:
            Parsed and validated JSON dict with keys: action, reason, confidence, evidence.

        Raises:
            OpenAIProviderError: If the API call fails after all retries.
        """
        if self._client is None:
            logger.warning("OpenAIProvider: No API client; returning mock response")
            return self._mock_response()

        start_time = time.perf_counter()

        try:
            result = self._retry_manager.execute(
                lambda: self._call_api(prompt)
            )
            raw_response = result.value
        except MaxRetriesExceededError as exc:
            raise OpenAIProviderError(
                f"OpenAI API failed after {exc.attempts} attempts: {exc.last_error}"
            ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Parse the response
        parse_result: ParseResult = self._output_parser.parse(raw_response)

        logger.info(
            "OpenAIProvider: response received",
            extra={
                "model": self._model,
                "latency_ms": round(latency_ms, 2),
                "repair_applied": parse_result.repair_applied,
                "repair_stage": parse_result.repair_stage,
                "action": parse_result.action,
                "confidence": parse_result.confidence,
                "cache_hit": prompt.is_cache_hit,
            },
        )

        return parse_result.parsed

    def _call_api(self, prompt: BuiltPrompt) -> str:
        """Execute a single OpenAI API call.

        Args:
            prompt: BuiltPrompt with system and user content.

        Returns:
            Raw text response string from OpenAI.

        Raises:
            Exception: On API failure (will be caught by RetryManager).
        """
        messages = [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.user_prompt},
        ]

        response = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=self._model,
            messages=messages,
            max_tokens=prompt.api_params.get("max_tokens", 150),
            temperature=prompt.api_params.get("temperature", 0.0),
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or ""

    @staticmethod
    def _read_api_key() -> str | None:
        """Read OpenAI API key from environment.

        Returns:
            API key string or None if not set.
        """
        import os
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            logger.warning("OPENAI_API_KEY not set in environment")
        return key

    def _init_client(self) -> Any | None:
        """Initialize the OpenAI client SDK.

        Returns:
            OpenAI client instance or None if SDK not available or key missing.
        """
        if not self._api_key:
            return None
        try:
            import openai  # type: ignore[import-untyped]
            return openai.OpenAI(api_key=self._api_key, timeout=self._timeout_secs)
        except ImportError:
            logger.warning("openai SDK not installed. Install: pip install openai")
            return None
        except Exception as exc:
            logger.error("OpenAIProvider: client init failed", extra={"error": str(exc)})
            return None

    @staticmethod
    def _mock_response() -> dict[str, Any]:
        """Return a deterministic mock response when no client is available.

        Returns:
            Safe fallback routing response.
        """
        return {
            "action": "DELIVER_SILENTLY",
            "reason": "OpenAI API unavailable; safe default applied.",
            "confidence": 0.50,
            "evidence": [],
        }

    @property
    def model(self) -> str:
        """Return the OpenAI model identifier."""
        return self._model

    @property
    def is_available(self) -> bool:
        """Return True if the OpenAI client is ready for API calls."""
        return self._client is not None
