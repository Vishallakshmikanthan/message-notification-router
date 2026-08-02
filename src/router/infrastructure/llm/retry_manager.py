"""Retry Manager — exponential backoff with full jitter for LLM API resilience.

Implements the Rate-Limit Resilience & API Optimization strategy from performance.md §5:
- Token-bucket style retry logic with exponential backoff.
- Full jitter to prevent thundering-herd problem.
- Max 3 retry attempts before triggering rule-based fallback.

Algorithm (performance.md §5):
    Sleep Time = random_uniform(0, min(MaxBackoff, Base × 2^attempt))
    Base Backoff: 100 ms
    Max Backoff: 2,000 ms
    Max Retries: 3

Spec: performance.md §5 (Rate-Limit Resilience & API Optimization).
      llm_strategy.md §2 (Bounded Latency guarantee).
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Algorithm parameters (performance.md §5)
_BASE_BACKOFF_MS = 100.0
_MAX_BACKOFF_MS = 2_000.0
_MAX_RETRIES = 3

# Retryable HTTP status codes
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class RetryAttempt:
    """Record of a single retry attempt.

    Attributes:
        attempt_number: 1-indexed attempt count.
        error_type: Exception class name.
        error_message: Error description.
        sleep_ms: Backoff time applied before the next attempt.
        timestamp_ms: Epoch milliseconds of this attempt.
    """

    attempt_number: int
    error_type: str
    error_message: str
    sleep_ms: float
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000)


@dataclass
class RetryResult:
    """Result of a retry-managed operation.

    Attributes:
        success: Whether the operation ultimately succeeded.
        value: Return value on success (None on failure).
        attempts: List of all attempt records.
        total_duration_ms: Total time including all backoffs.
    """

    success: bool
    value: Any
    attempts: list[RetryAttempt]
    total_duration_ms: float

    @property
    def attempt_count(self) -> int:
        """Number of attempts made (including the final successful/failed one)."""
        return len(self.attempts)

    @property
    def was_retried(self) -> bool:
        """True if more than one attempt was made."""
        return self.attempt_count > 1


class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts are exhausted without success.

    Attributes:
        attempts: List of all retry attempt records.
        last_error: The last exception that caused the failure.
    """

    def __init__(self, attempts: list[RetryAttempt], last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Max retries ({len(attempts)}) exceeded. "
            f"Last error: {type(last_error).__name__}: {last_error}"
        )


class RetryManager:
    """Exponential backoff retry manager with full jitter.

    Wraps synchronous callable operations with retry logic appropriate for
    LLM API calls (rate limits, transient server errors).

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        base_backoff_ms: Base backoff time in milliseconds (default 100ms).
        max_backoff_ms: Maximum backoff ceiling in milliseconds (default 2000ms).
        retryable_exceptions: Exception types that should trigger retries.
                              Defaults to Exception if not specified.
        jitter: If True, apply full jitter (random_uniform). If False, use
                pure exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = _MAX_RETRIES,
        base_backoff_ms: float = _BASE_BACKOFF_MS,
        max_backoff_ms: float = _MAX_BACKOFF_MS,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
        jitter: bool = True,
    ) -> None:
        """Initialize the RetryManager.

        Args:
            max_retries: Maximum retry attempts.
            base_backoff_ms: Base backoff in milliseconds.
            max_backoff_ms: Maximum backoff in milliseconds.
            retryable_exceptions: Exception types to retry on.
            jitter: Whether to apply full jitter to backoff.
        """
        self._max_retries = max_retries
        self._base_backoff_ms = base_backoff_ms
        self._max_backoff_ms = max_backoff_ms
        self._retryable_exceptions = retryable_exceptions or (Exception,)
        self._jitter = jitter
        logger.info(
            "RetryManager initialized",
            extra={
                "max_retries": max_retries,
                "base_backoff_ms": base_backoff_ms,
                "max_backoff_ms": max_backoff_ms,
                "jitter": jitter,
            },
        )

    def execute(self, fn: Callable[[], Any]) -> RetryResult:
        """Execute a callable with retry logic.

        Args:
            fn: Zero-argument callable to execute with retries.

        Returns:
            RetryResult with success status, value, and attempt history.

        Raises:
            MaxRetriesExceededError: If all retries are exhausted.
        """
        start_time = time.perf_counter()
        attempts: list[RetryAttempt] = []
        last_error: Exception | None = None

        for attempt_num in range(1, self._max_retries + 2):  # +2 = initial + retries
            try:
                value = fn()
                total_ms = (time.perf_counter() - start_time) * 1000.0

                if attempts:
                    logger.info(
                        "RetryManager: succeeded after retries",
                        extra={"attempt": attempt_num, "total_ms": round(total_ms, 2)},
                    )
                return RetryResult(
                    success=True,
                    value=value,
                    attempts=attempts,
                    total_duration_ms=round(total_ms, 2),
                )

            except self._retryable_exceptions as exc:
                last_error = exc
                retries_left = self._max_retries - len(attempts)

                if retries_left <= 0:
                    # All retries exhausted
                    break

                sleep_ms = self._compute_sleep_ms(len(attempts))
                attempt_record = RetryAttempt(
                    attempt_number=attempt_num,
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:200],
                    sleep_ms=sleep_ms,
                )
                attempts.append(attempt_record)

                logger.warning(
                    "RetryManager: attempt failed, backing off",
                    extra={
                        "attempt": attempt_num,
                        "error": type(exc).__name__,
                        "sleep_ms": round(sleep_ms, 1),
                        "retries_left": retries_left - 1,
                    },
                )
                time.sleep(sleep_ms / 1000.0)

        # All attempts exhausted
        total_ms = (time.perf_counter() - start_time) * 1000.0
        raise MaxRetriesExceededError(attempts, last_error or Exception("Unknown error"))

    def _compute_sleep_ms(self, attempt_index: int) -> float:
        """Compute sleep time using exponential backoff with optional full jitter.

        Formula (performance.md §5):
            sleep = random_uniform(0, min(MaxBackoff, Base × 2^attempt))

        Args:
            attempt_index: Zero-based attempt index.

        Returns:
            Sleep time in milliseconds.
        """
        exponential_cap = min(
            self._max_backoff_ms,
            self._base_backoff_ms * (2 ** attempt_index),
        )
        if self._jitter:
            return random.uniform(0.0, exponential_cap)
        return exponential_cap

    @property
    def max_retries(self) -> int:
        """Return maximum retry count."""
        return self._max_retries
