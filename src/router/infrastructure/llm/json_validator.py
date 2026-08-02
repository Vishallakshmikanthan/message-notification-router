"""JSON Validator — Pydantic schema enforcement for LLM output validation.

Implements Stage 2 and Stage 3 of the Output Validation & Self-Healing Architecture
from prompt_architecture.md §5:
- Validates action enum membership (NOTIFY_IMMEDIATELY, DELIVER_SILENTLY, etc.)
- Validates confidence bounds [0.0, 1.0]
- Validates evidence_keys exist in the provided input context (anti-hallucination)
- Provides schema coercion and auto-repair via Pydantic

Spec: prompt_architecture.md §5 Stage 2 & Stage 3.
      deployment.md §2 (Prompt Injection & Adversarial Isolation).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class RoutingAction(str, Enum):
    """Strictly enforced routing action enum.

    These are the ONLY permitted action values across the entire system.
    """

    NOTIFY_IMMEDIATELY = "NOTIFY_IMMEDIATELY"
    DELIVER_SILENTLY = "DELIVER_SILENTLY"
    SUMMARIZE_IN_BATCH = "SUMMARIZE_IN_BATCH"
    DO_NOT_DISTURB = "DO_NOT_DISTURB"


class LLMOutputSchema(BaseModel):
    """Pydantic schema for LLM routing decision output.

    Enforces:
    - action: Must be a valid RoutingAction enum value.
    - reason: Non-empty string, max 200 characters.
    - confidence: Float in [0.0, 1.0].
    - evidence: List of string keys (may be empty).

    All fields undergo automatic coercion before validation.
    """

    action: RoutingAction
    reason: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> str:
        """Coerce action to uppercase string before enum validation.

        Args:
            v: Raw action value.

        Returns:
            Uppercase string.
        """
        if isinstance(v, str):
            return v.strip().upper()
        return str(v).upper()

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float:
        """Coerce confidence to float and clamp to [0.0, 1.0].

        Args:
            v: Raw confidence value.

        Returns:
            Clamped float.
        """
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, f))

    @field_validator("reason", mode="before")
    @classmethod
    def coerce_reason(cls, v: Any) -> str:
        """Coerce reason to string and strip whitespace.

        Args:
            v: Raw reason value.

        Returns:
            Stripped string.
        """
        if v is None:
            return "Routing decision applied."
        return str(v).strip()[:200]

    @field_validator("evidence", mode="before")
    @classmethod
    def coerce_evidence(cls, v: Any) -> list[str]:
        """Coerce evidence to list of strings.

        Args:
            v: Raw evidence value.

        Returns:
            List of strings.
        """
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(item) for item in v if item is not None]
        return []

    def to_dict(self) -> dict[str, Any]:
        """Export as plain dictionary.

        Returns:
            Dict with action string, reason, confidence, and evidence.
        """
        return {
            "action": self.action.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


class ValidationResult:
    """Result of a JSON validation attempt.

    Attributes:
        is_valid: Whether validation passed.
        validated_data: Validated and coerced data dict (or None on failure).
        errors: List of validation error descriptions.
        coercion_applied: Whether Pydantic coercion was needed.
        hallucinated_keys: Evidence keys not found in provided context.
    """

    __slots__ = (
        "is_valid",
        "validated_data",
        "errors",
        "coercion_applied",
        "hallucinated_keys",
    )

    def __init__(
        self,
        is_valid: bool,
        validated_data: dict[str, Any] | None,
        errors: list[str],
        coercion_applied: bool = False,
        hallucinated_keys: list[str] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.validated_data = validated_data
        self.errors = errors
        self.coercion_applied = coercion_applied
        self.hallucinated_keys = hallucinated_keys or []


class JSONValidator:
    """Pydantic-backed schema validator for LLM output JSON.

    Validates routing decision JSON against the LLMOutputSchema contract and
    performs anti-hallucination evidence key grounding checks.

    Args:
        context_evidence_keys: Set of valid evidence keys from the input context.
                               Used for anti-hallucination validation.
    """

    def __init__(self, context_evidence_keys: list[str] | None = None) -> None:
        """Initialize JSONValidator.

        Args:
            context_evidence_keys: Valid evidence keys from the current context.
        """
        self._context_keys = set(context_evidence_keys or [])
        logger.info(
            "JSONValidator initialized",
            extra={"context_keys_count": len(self._context_keys)},
        )

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate a JSON dict against the LLMOutputSchema.

        Steps:
        1. Pydantic schema validation with automatic coercion.
        2. Evidence anti-hallucination check (if context keys provided).
        3. Confidence bounds verification.

        Args:
            data: Parsed JSON dict to validate.

        Returns:
            ValidationResult with is_valid, validated_data, and errors.
        """
        errors: list[str] = []
        hallucinated: list[str] = []

        # Step 1: Pydantic validation with coercion
        try:
            validated = LLMOutputSchema.model_validate(data)
            coercion_applied = (
                validated.action.value != str(data.get("action", "")).upper()
                or validated.confidence != float(data.get("confidence", 0.5))
            )
        except Exception as exc:
            error_msg = self._extract_pydantic_errors(exc)
            errors.extend(error_msg)
            logger.warning(
                "JSONValidator: Pydantic validation failed",
                extra={"errors": errors[:3]},
            )
            return ValidationResult(
                is_valid=False,
                validated_data=None,
                errors=errors,
            )

        # Step 2: Anti-hallucination evidence key check
        if self._context_keys:
            for key in validated.evidence:
                if key and key not in self._context_keys:
                    hallucinated.append(key)
                    errors.append(f"HALLUCINATED_EVIDENCE_KEY:{key}")

        # Step 3: Confidence bounds (already enforced by Pydantic but log it)
        if not (0.0 <= validated.confidence <= 1.0):
            errors.append(f"CONFIDENCE_OUT_OF_BOUNDS:{validated.confidence}")

        is_valid = len([e for e in errors if "HALLUCINATED" not in e]) == 0

        logger.debug(
            "JSONValidator: validation complete",
            extra={
                "is_valid": is_valid,
                "action": validated.action.value,
                "confidence": validated.confidence,
                "hallucinated_count": len(hallucinated),
                "errors_count": len(errors),
            },
        )

        return ValidationResult(
            is_valid=is_valid,
            validated_data=validated.to_dict(),
            errors=errors,
            coercion_applied=coercion_applied,
            hallucinated_keys=hallucinated,
        )

    def update_context_keys(self, keys: list[str]) -> None:
        """Update the set of valid context evidence keys.

        Args:
            keys: New list of valid evidence key strings.
        """
        self._context_keys = set(keys)
        logger.debug(
            "JSONValidator: context keys updated",
            extra={"count": len(self._context_keys)},
        )

    @staticmethod
    def _extract_pydantic_errors(exc: Exception) -> list[str]:
        """Extract human-readable error strings from a Pydantic ValidationError.

        Args:
            exc: Pydantic ValidationError or other exception.

        Returns:
            List of error strings.
        """
        try:
            # Pydantic v2 ValidationError
            if hasattr(exc, "errors"):
                return [
                    f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
                    for e in exc.errors()  # type: ignore[attr-defined]
                ]
        except Exception:
            pass
        return [str(exc)]
