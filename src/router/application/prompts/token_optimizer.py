"""Token Optimizer — compact signal encoding for LLM context efficiency.

Implements the Token & Cost Minimization Strategy from performance.md §6:
1. Compact Key-Value Signal Encoding — signal bundles as dense key-value pairs.
2. Strict Output Token Caps — completion length capped at 150 tokens.
3. Structured Signal Encoding — converts verbose natural language to compact format.

Saves ~35% on prompt tokens compared to verbose natural-language signal descriptions.

Example output:
  ``urgency:0.82|rel:0.91|dnd:false|spam:0.03|vip:true|known:true``

Spec: performance.md §6 (Token & Cost Minimization Strategy).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Output token cap (performance.md §6)
MAX_COMPLETION_TOKENS = 150

# Characters per token estimation
_CHARS_PER_TOKEN = 3.5

# Signal field short names mapping
_SIGNAL_SHORT_NAMES: Dict[str, str] = {
    "urgency_score": "urgency",
    "spam_score": "spam",
    "scam_score": "scam",
    "trust_score": "trust",
    "relationship_closeness": "rel",
    "is_quiet_hours": "dnd",
    "sender_is_vip": "vip",
    "sender_in_address_book": "known",
    "notification_fatigue_score": "fatigue",
    "historical_open_rate": "open_rate",
    "media_type": "media",
    "message_type": "msg_type",
    "user_activity_status": "activity",
    "hour_of_day": "hour",
    "personal_sender_known": "personal",
}


@dataclass(frozen=True)
class TokenBudgetAllocation:
    """Immutable token budget allocation for a single LLM call.

    Attributes:
        system_tokens: Budget for system prompt (default 400).
        few_shot_tokens: Budget for few-shot exemplars (default 600).
        context_tokens: Budget for retrieved memory + context (default 1600).
        message_tokens: Budget for current message + signals (default 800).
        completion_tokens: Max completion tokens (default 150).
        total_input_tokens: Sum of all input sections.
    """

    system_tokens: int = 400
    few_shot_tokens: int = 600
    context_tokens: int = 1_600
    message_tokens: int = 800
    completion_tokens: int = MAX_COMPLETION_TOKENS

    @property
    def total_input_tokens(self) -> int:
        """Total input token budget."""
        return self.system_tokens + self.few_shot_tokens + self.context_tokens + self.message_tokens


class TokenOptimizer:
    """Signal bundle token optimizer.

    Converts signal dictionaries into compact, pipe-delimited key-value strings
    that minimize prompt token usage while preserving all critical information.

    Also manages output token capping directives sent to the LLM API.

    Args:
        max_completion_tokens: Maximum completion tokens to request (default 150).
        budget: Token budget allocation (uses default 4096-window allocation if None).
    """

    def __init__(
        self,
        max_completion_tokens: int = MAX_COMPLETION_TOKENS,
        budget: Optional[TokenBudgetAllocation] = None,
    ) -> None:
        """Initialize TokenOptimizer.

        Args:
            max_completion_tokens: Cap for model completion length.
            budget: Token budget allocation object.
        """
        self._max_completion_tokens = max_completion_tokens
        self._budget = budget or TokenBudgetAllocation(
            completion_tokens=max_completion_tokens
        )
        logger.info(
            "TokenOptimizer initialized",
            extra={
                "max_completion_tokens": max_completion_tokens,
                "total_input_budget": self._budget.total_input_tokens,
            },
        )

    @property
    def max_completion_tokens(self) -> int:
        """Return maximum completion token count."""
        return self._max_completion_tokens

    @property
    def budget(self) -> TokenBudgetAllocation:
        """Return token budget allocation."""
        return self._budget

    def encode_signals(self, signal_dict: Dict[str, Any]) -> str:
        """Encode a signal dictionary into a compact pipe-delimited string.

        Converts verbose signal payloads into dense KV pairs such as:
        ``urgency:0.82|rel:0.91|dnd:false|spam:0.03|vip:true``

        Args:
            signal_dict: Raw signal key-value pairs.

        Returns:
            Compact encoded signal string.
        """
        parts: List[str] = []
        for long_key, short_key in _SIGNAL_SHORT_NAMES.items():
            val = signal_dict.get(long_key)
            if val is None:
                continue
            encoded = self._encode_value(val)
            parts.append(f"{short_key}:{encoded}")

        # Include any extra keys not in the standard map
        standard_keys = set(_SIGNAL_SHORT_NAMES.keys())
        for key, val in signal_dict.items():
            if key not in standard_keys:
                encoded = self._encode_value(val)
                parts.append(f"{key[:8]}:{encoded}")

        result = "|".join(parts) if parts else "signals:none"
        logger.debug(
            "Signals encoded",
            extra={"original_keys": len(signal_dict), "encoded_length": len(result)},
        )
        return result

    def estimate_tokens(self, text: str) -> int:
        """Estimate the token count of a text string.

        Uses conservative character-per-token ratio (~3.5 chars/token).

        Args:
            text: Input text string.

        Returns:
            Estimated token count.
        """
        return max(1, int(len(text) / _CHARS_PER_TOKEN))

    def fits_budget(self, text: str, section: str = "context") -> bool:
        """Check whether a text section fits within its allocated budget.

        Args:
            text: Text to check.
            section: Budget section name ('system'|'few_shot'|'context'|'message').

        Returns:
            True if text fits within the section budget.
        """
        budget_map = {
            "system": self._budget.system_tokens,
            "few_shot": self._budget.few_shot_tokens,
            "context": self._budget.context_tokens,
            "message": self._budget.message_tokens,
        }
        limit = budget_map.get(section, self._budget.context_tokens)
        estimated = self.estimate_tokens(text)
        return estimated <= limit

    def build_api_params(self) -> Dict[str, Any]:
        """Build LLM API parameters with token constraints.

        Returns:
            Dict with max_tokens and stop sequences for provider API calls.
        """
        return {
            "max_tokens": self._max_completion_tokens,
            "temperature": 0.0,  # Deterministic output
        }

    @staticmethod
    def _encode_value(val: Any) -> str:
        """Encode a signal value as a compact string.

        Args:
            val: Signal value (float, bool, str, int, etc.).

        Returns:
            Compact string representation.
        """
        if isinstance(val, float):
            return f"{val:.2f}"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, int):
            return str(val)
        if val is None:
            return "null"
        # Truncate long strings
        s = str(val)
        return s[:12] if len(s) > 12 else s
