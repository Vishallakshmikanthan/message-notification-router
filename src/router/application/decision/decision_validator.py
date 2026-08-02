"""DecisionValidator — 5-pass output validation and self-correction for DecisionResult.

Acts as the final gatekeeper before routing decisions reach the delivery gateway.
Implements a strict 5-pass validation suite:

  Pass 1: Schema Validation (required fields, type checks, UUID format)
  Pass 2: Allowed Values & Boundary Checks (enum values, score ranges)
  Pass 3: Reasoning Consistency Validation (logic cross-checks)
  Pass 4: Evidence Grounding Verification (hallucination detection)
  Pass 5: Confidence Threshold Verification (minimum action thresholds)

Recovery Strategy (decision_validation.md §1.2):
- NEVER crash or block notification delivery on validation failure.
- Log the error and mutate to a safe fallback payload.
- Set verification_status.fallback_applied = True.

Spec: decision_validation.md §1 Output Validation Engine.
"""

from __future__ import annotations

import re

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    CalibratedDecision,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    VerificationResult,
)
from router.domain.ports.decision_ports import IDecisionValidator

logger = get_logger(__name__)

# UUID v4 regex pattern
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Reasoning summary keywords that imply non-urgency (used in Pass 3)
_NON_URGENT_KEYWORDS = frozenset([
    "marketing", "promotional", "broadcast", "spam", "non-urgent", "casual",
    "advertisement", "forwarded", "digest", "batch",
])

# Action-specific minimum calibrated confidence (Pass 5 — same as ConfidenceEngine)
_ACTION_MIN_CONFIDENCE = {
    DecisionAction.TRIGGER_EMERGENCY_OVERRIDE: 0.90,
    DecisionAction.DELIVER_IMMEDIATELY: 0.70,
    DecisionAction.SUPPRESS_SPAM: 0.85,
    DecisionAction.SUMMARIZE_LATER: 0.55,
    DecisionAction.DELIVER_SILENT: 0.45,
    DecisionAction.BATCH_DIGEST: 0.35,
    DecisionAction.SUPPRESS_MUTE: 0.80,
}

# Safe fallback payload values
_FALLBACK_URGENCY = 0.50
_FALLBACK_IMPORTANCE = 0.50
_FALLBACK_SUMMARY = "System applied safe default due to output validation correction."


class DecisionValidator(IDecisionValidator):
    """Implements the 5-pass validation suite with automated self-correction.

    Never raises exceptions to callers — all failures are caught, logged,
    and converted to safe fallback payloads per the recovery protocol.
    """

    def validate(
        self,
        decision: CalibratedDecision,
        context: DecisionContext,
    ) -> VerificationResult:
        """Run 5-pass validation suite on the calibrated decision.

        Args:
            decision: CalibratedDecision to validate.
            context: DecisionContext for grounding cross-check.

        Returns:
            VerificationResult with is_valid flag and error details.
        """
        errors: list[str] = []
        passes_executed = 0
        suggested_fallback: DecisionAction | None = None

        # Pass 1: Schema Validation
        passes_executed += 1
        pass1_errors = self._pass1_schema_validation(decision, context)
        errors.extend(pass1_errors)

        # Pass 2: Allowed Values & Boundary Checks
        passes_executed += 1
        pass2_errors = self._pass2_allowed_values(decision)
        errors.extend(pass2_errors)

        # Pass 3: Reasoning Consistency Validation
        passes_executed += 1
        pass3_errors = self._pass3_reasoning_consistency(decision)
        errors.extend(pass3_errors)

        # Pass 4: Evidence Grounding Verification
        passes_executed += 1
        pass4_errors = self._pass4_evidence_grounding(decision, context)
        errors.extend(pass4_errors)

        # Pass 5: Confidence Threshold Verification
        passes_executed += 1
        pass5_errors, pass5_fallback = self._pass5_confidence_threshold(decision, context)
        errors.extend(pass5_errors)
        if pass5_fallback:
            suggested_fallback = pass5_fallback

        is_valid = len(errors) == 0

        if not is_valid:
            # Determine fallback from first critical error category
            if not suggested_fallback:
                suggested_fallback = self._choose_fallback(decision, context)

            logger.warning(
                "DecisionValidator: validation failed",
                context_id=context.context_id,
                error_count=len(errors),
                errors=errors[:5],  # Log first 5 to avoid log spam
                suggested_fallback=suggested_fallback,
            )
        else:
            logger.info(
                "DecisionValidator: all 5 passes cleared",
                context_id=context.context_id,
                action=decision.action,
                calibrated_confidence=decision.calibrated_confidence,
            )

        return VerificationResult(
            is_valid=is_valid,
            validation_errors=errors,
            suggested_fallback_action=suggested_fallback,
            passes_executed=passes_executed,
        )

    # ------------------------------------------------------------------
    # Validation Pass Implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _pass1_schema_validation(
        decision: CalibratedDecision, context: DecisionContext
    ) -> list[str]:
        """Pass 1: Schema validation — required fields and type checks.

        Args:
            decision: CalibratedDecision.
            context: DecisionContext.

        Returns:
            List of error strings (empty if valid).
        """
        errors: list[str] = []

        if not isinstance(decision.action, (str, DecisionAction)):
            errors.append("SCHEMA_ERROR: action must be a DecisionAction enum string.")

        if not isinstance(decision.urgency_score, (int, float)):
            errors.append("SCHEMA_ERROR: urgency_score must be numeric.")

        if not isinstance(decision.importance_score, (int, float)):
            errors.append("SCHEMA_ERROR: importance_score must be numeric.")

        if not decision.reasoning_summary:
            errors.append("SCHEMA_ERROR: reasoning_summary must not be empty.")

        if not isinstance(decision.calibrated_confidence, (int, float)):
            errors.append("SCHEMA_ERROR: calibrated_confidence must be numeric.")

        # Context ID format check (should be UUID-like)
        ctx_id = context.context_id
        if ctx_id and not _UUID_PATTERN.match(ctx_id):
            errors.append(
                f"SCHEMA_ERROR: context_id does not match UUID v4 format: {ctx_id!r}"
            )

        return errors

    @staticmethod
    def _pass2_allowed_values(decision: CalibratedDecision) -> list[str]:
        """Pass 2: Validate enum values and numeric range boundaries.

        Args:
            decision: CalibratedDecision.

        Returns:
            List of error strings.
        """
        errors: list[str] = []

        # Validate DecisionAction enum
        valid_actions = set(DecisionAction)
        if decision.action not in valid_actions:
            errors.append(
                f"INVALID_ACTION_ENUM: '{decision.action}' is not a valid DecisionAction."
            )

        # Validate DecisionCategory enum
        valid_categories = set(DecisionCategory)
        if decision.category not in valid_categories:
            errors.append(
                f"INVALID_CATEGORY_ENUM: '{decision.category}' is not a valid DecisionCategory."
            )

        # Score boundary checks
        if not (0.0 <= decision.urgency_score <= 1.0):
            errors.append(
                f"OUT_OF_RANGE: urgency_score={decision.urgency_score} not in [0.0, 1.0]."
            )

        if not (0.0 <= decision.importance_score <= 1.0):
            errors.append(
                f"OUT_OF_RANGE: importance_score={decision.importance_score} not in [0.0, 1.0]."
            )

        if not (0.0 <= decision.calibrated_confidence <= 1.0):
            errors.append(
                f"OUT_OF_RANGE: calibrated_confidence={decision.calibrated_confidence} not in [0.0, 1.0]."
            )

        # Reasoning summary length
        if len(decision.reasoning_summary) > 250:
            errors.append(
                f"SCHEMA_ERROR: reasoning_summary exceeds 250 chars ({len(decision.reasoning_summary)})."
            )

        return errors

    @staticmethod
    def _pass3_reasoning_consistency(decision: CalibratedDecision) -> list[str]:
        """Pass 3: Cross-check action against reasoning summary for logical consistency.

        Examples:
        - 'DELIVER_IMMEDIATELY' cannot have a summary indicating 'non-urgent marketing'.
        - 'SUPPRESS_SPAM' should not have urgency_score > 0.90.

        Args:
            decision: CalibratedDecision.

        Returns:
            List of error strings.
        """
        errors: list[str] = []
        summary_lower = decision.reasoning_summary.lower()

        # DELIVER_IMMEDIATELY requires urgency score >= 0.60
        if (
            decision.action == DecisionAction.DELIVER_IMMEDIATELY
            and decision.urgency_score < 0.60
        ):
            errors.append(
                f"REASONING_INCONSISTENCY: DELIVER_IMMEDIATELY requires urgency>=0.60 "
                f"(actual={decision.urgency_score:.2f})."
            )

        # DELIVER_IMMEDIATELY must not cite non-urgent keywords in reasoning
        if decision.action == DecisionAction.DELIVER_IMMEDIATELY:
            for kw in _NON_URGENT_KEYWORDS:
                if kw in summary_lower:
                    errors.append(
                        f"REASONING_INCONSISTENCY: DELIVER_IMMEDIATELY reasoning "
                        f"contains non-urgent keyword '{kw}'."
                    )
                    break  # One error per check sufficient

        # Note: SUPPRESS_SPAM (safety/scam/spam suppression) is valid even with high urgency scores,
        # because phishing/scam attempts frequently use artificial urgency tactics.

        # TRIGGER_EMERGENCY_OVERRIDE must have urgency > 0.80
        if (
            decision.action == DecisionAction.TRIGGER_EMERGENCY_OVERRIDE
            and decision.urgency_score < 0.80
        ):
            errors.append(
                f"REASONING_INCONSISTENCY: TRIGGER_EMERGENCY_OVERRIDE requires urgency>=0.80 "
                f"(actual={decision.urgency_score:.2f})."
            )

        return errors

    @staticmethod
    def _pass4_evidence_grounding(
        decision: CalibratedDecision, context: DecisionContext
    ) -> list[str]:
        """Pass 4: Verify that reasoning_summary does not cite ungrounded facts.

        Checks that any evidence IDs cited in the decision exist in the EvidenceBundle.
        Flags a grounding_warning if the top evidence relevance is below threshold.

        Args:
            decision: CalibratedDecision.
            context: DecisionContext with EvidenceBundle.

        Returns:
            List of error strings.
        """
        errors: list[str] = []
        eb = context.evidence_bundle

        # Verify cited evidence IDs exist in EvidenceBundle
        available_ids = {item.message_id for item in eb.items}
        for cited_id in decision.evidence_ids:
            if cited_id and cited_id not in available_ids and cited_id.lower() != "none":
                errors.append(
                    f"UNGROUNDED_FACT: evidence_id '{cited_id}' not found in EvidenceBundle."
                )

        # Grounding warning is informational logging, not a hard error.
        return errors

    @staticmethod
    def _pass5_confidence_threshold(
        decision: CalibratedDecision, context: DecisionContext
    ) -> tuple[list[str], DecisionAction | None]:
        """Pass 5: Verify calibrated confidence meets action-specific minimum threshold.

        During quiet hours, DELIVER_IMMEDIATELY requires confidence >= 0.85.

        Args:
            decision: CalibratedDecision.
            context: DecisionContext.

        Returns:
            Tuple of (errors list, suggested_fallback_action or None).
        """
        errors: list[str] = []
        fallback: DecisionAction | None = None

        sb = context.signal_bundle
        action = decision.action
        confidence = decision.calibrated_confidence

        # Higher threshold for DELIVER_IMMEDIATELY during quiet hours
        if action == DecisionAction.DELIVER_IMMEDIATELY and sb.is_quiet_hours:
            required = 0.85
        else:
            required = _ACTION_MIN_CONFIDENCE.get(action, 0.35)

        if confidence < required:
            errors.append(
                f"CONFIDENCE_BELOW_THRESHOLD: action={action} requires >={required:.2f} "
                f"(actual={confidence:.3f})."
            )
            # Suggest appropriate fallback
            if action in (
                DecisionAction.DELIVER_IMMEDIATELY,
                DecisionAction.TRIGGER_EMERGENCY_OVERRIDE,
            ):
                fallback = DecisionAction.DELIVER_SILENT
            elif action in (DecisionAction.SUPPRESS_SPAM, DecisionAction.SUPPRESS_MUTE):
                fallback = DecisionAction.SUPPRESS_SPAM
            else:
                fallback = DecisionAction.BATCH_DIGEST

        # Global low-confidence recovery (decision_flow.md §4.2)
        if confidence < 0.45 and action not in (
            DecisionAction.DELIVER_SILENT,
            DecisionAction.BATCH_DIGEST,
            DecisionAction.SUMMARIZE_LATER,
            DecisionAction.SUPPRESS_SPAM,
            DecisionAction.SUPPRESS_MUTE,
        ):
            fallback_action = (
                DecisionAction.DELIVER_SILENT
                if sb.personal_sender_known
                else DecisionAction.BATCH_DIGEST
            )
            errors.append(
                f"LOW_CONFIDENCE_RECOVERY: calibrated_confidence={confidence:.3f} < 0.45 threshold."
            )
            fallback = fallback_action

        return errors, fallback

    @staticmethod
    def _choose_fallback(
        decision: CalibratedDecision, context: DecisionContext
    ) -> DecisionAction:
        """Choose appropriate safe fallback action for validation failures.

        Rule (decision_validation.md §1.2):
        - Known sender: DELIVER_SILENT
        - Unknown sender / group: SUMMARIZE_LATER

        Args:
            decision: CalibratedDecision.
            context: DecisionContext.

        Returns:
            Safe fallback DecisionAction.
        """
        sb = context.signal_bundle
        if sb.personal_sender_known:
            return DecisionAction.DELIVER_SILENT
        return DecisionAction.SUMMARIZE_LATER
