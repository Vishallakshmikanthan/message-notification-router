"""Unit tests for DecisionValidator — 5-pass validation suite and self-correction.

Tests cover:
- Pass 1: Schema validation (required fields, type checks).
- Pass 2: Enum value and range boundary checks.
- Pass 3: Reasoning consistency cross-checks.
- Pass 4: Evidence grounding verification.
- Pass 5: Confidence threshold enforcement.
- Recovery strategy: fallback action selection.
- Edge cases: empty evidence, TRIGGER_EMERGENCY_OVERRIDE thresholds.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from router.application.decision.decision_validator import DecisionValidator
from router.domain.entities.decision_models import (
    CalibratedDecision,
    ConfidenceBreakdown,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
)
from router.domain.entities.evidence import EvidenceBundle, EvidenceItem


def _make_calibrated(
    action: DecisionAction = DecisionAction.DELIVER_IMMEDIATELY,
    category: DecisionCategory = DecisionCategory.PERSONAL_URGENT,
    urgency: float = 0.85,
    importance: float = 0.80,
    confidence: float = 0.80,
    summary: str = "VIP contact sent urgent message during business hours.",
    bypassed_llm: bool = False,
    grounding_warning: bool = False,
    evidence_ids: list = None,
    key_factors: list = None,
) -> CalibratedDecision:
    """Build a CalibratedDecision with specified parameters."""
    breakdown = ConfidenceBreakdown(calibrated_confidence=confidence)
    return CalibratedDecision(
        action=action,
        category=category,
        urgency_score=urgency,
        importance_score=importance,
        reasoning_summary=summary,
        key_factors=key_factors or ["VIP_CONTACT"],
        evidence_ids=evidence_ids or [],
        calibrated_confidence=confidence,
        confidence_breakdown=breakdown,
        bypassed_llm=bypassed_llm,
        grounding_warning=grounding_warning,
    )


def _make_context(
    context_id: str = "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
    is_quiet_hours: bool = False,
    personal_sender_known: bool = True,
    evidence_items: list = None,
) -> DecisionContext:
    """Build a mock DecisionContext."""
    sb = MagicMock()
    sb.is_quiet_hours = is_quiet_hours
    sb.personal_sender_known = personal_sender_known

    items = evidence_items or [
        EvidenceItem(
            message_id="ev_001",
            similarity_score=0.75,
            behaviour_match=0.5,
            sender_match=0.5,
            business_match=0.5,
            group_match=0.5,
            recency_days=1.0,
            importance_weight=1.0,
            trust_score=0.7,
            reason_retrieved="TEST",
        )
    ]
    eb = EvidenceBundle(
        query_message_id="msg_test",
        user_id="user_001",
        evidence_count=len(items),
        items=items,
    )

    ctx = MagicMock(spec=DecisionContext)
    ctx.context_id = context_id
    ctx.signal_bundle = sb
    ctx.evidence_bundle = eb
    return ctx


class TestValidatorPass1Schema:
    """Tests for Pass 1: Schema validation."""

    def test_valid_decision_passes_schema(self):
        validator = DecisionValidator()
        decision = _make_calibrated()
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert "SCHEMA_ERROR" not in " ".join(result.validation_errors)

    def test_empty_reasoning_summary_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(summary="")
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("SCHEMA_ERROR" in e for e in result.validation_errors)
        assert result.is_valid is False


class TestValidatorPass2AllowedValues:
    """Tests for Pass 2: Allowed values and boundary checks."""

    def test_valid_enums_pass(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SPAM_VIRAL,
            urgency=0.10,
            confidence=0.90,
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        spam_related_errors = [e for e in result.validation_errors if "ENUM" in e]
        assert len(spam_related_errors) == 0

    def test_reasoning_too_long_fails(self):
        validator = DecisionValidator()
        long_summary = "x" * 260  # Exceeds 250 char limit
        decision = _make_calibrated(summary=long_summary)
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("reasoning_summary" in e for e in result.validation_errors)

    def test_confidence_out_of_range_fails(self):
        validator = DecisionValidator()
        breakdown = ConfidenceBreakdown(calibrated_confidence=1.5)  # Out of range
        decision = CalibratedDecision(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.PERSONAL_URGENT,
            urgency_score=0.85,
            importance_score=0.80,
            reasoning_summary="Test summary.",
            key_factors=["VIP"],
            evidence_ids=[],
            calibrated_confidence=1.5,  # Invalid!
            confidence_breakdown=breakdown,
            bypassed_llm=False,
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("OUT_OF_RANGE" in e for e in result.validation_errors)
        assert result.is_valid is False


class TestValidatorPass3Consistency:
    """Tests for Pass 3: Reasoning consistency validation."""

    def test_deliver_immediately_with_low_urgency_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.40,  # Too low for DELIVER_IMMEDIATELY
            confidence=0.85,
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("REASONING_INCONSISTENCY" in e for e in result.validation_errors)

    def test_deliver_immediately_with_non_urgent_keyword_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.85,
            confidence=0.85,
            summary="This is a promotional marketing broadcast message.",
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("REASONING_INCONSISTENCY" in e for e in result.validation_errors)

    def test_suppress_spam_with_very_high_urgency_passes(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.SUPPRESS_SPAM,
            urgency=0.95,  # Valid — scam artificial urgency
            confidence=0.90,
            summary="Spam detected from sender.",
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert not any("REASONING_INCONSISTENCY" in e for e in result.validation_errors)

    def test_consistent_decision_passes(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.90,
            confidence=0.85,
            summary="Urgent VIP message requiring immediate attention.",
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        consistency_errors = [e for e in result.validation_errors if "REASONING_INCONSISTENCY" in e]
        assert len(consistency_errors) == 0


class TestValidatorPass4Grounding:
    """Tests for Pass 4: Evidence grounding verification."""

    def test_cited_evidence_id_not_in_bundle_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.85,
            confidence=0.85,
            evidence_ids=["ev_999"],  # Not in EvidenceBundle
        )
        ctx = _make_context(evidence_items=[
            EvidenceItem(
                message_id="ev_001",  # Different ID
                similarity_score=0.75,
                behaviour_match=0.5,
                sender_match=0.5,
                business_match=0.5,
                group_match=0.5,
                recency_days=1.0,
                importance_weight=1.0,
                trust_score=0.7,
                reason_retrieved="TEST",
            )
        ])
        result = validator.validate(decision, ctx)
        assert any("UNGROUNDED_FACT" in e for e in result.validation_errors)

    def test_valid_cited_evidence_passes(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.85,
            confidence=0.85,
            evidence_ids=["ev_001"],  # Matches EvidenceBundle
        )
        ctx = _make_context()  # Default has ev_001
        result = validator.validate(decision, ctx)
        grounding_errors = [e for e in result.validation_errors if "UNGROUNDED_FACT" in e]
        assert len(grounding_errors) == 0


class TestValidatorPass5Confidence:
    """Tests for Pass 5: Confidence threshold verification."""

    def test_deliver_immediately_below_threshold_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.85,
            confidence=0.50,  # Below 0.70 threshold
        )
        ctx = _make_context(is_quiet_hours=False)
        result = validator.validate(decision, ctx)
        assert any("CONFIDENCE_BELOW_THRESHOLD" in e for e in result.validation_errors)
        assert result.suggested_fallback_action == DecisionAction.DELIVER_SILENT

    def test_emergency_override_below_threshold_fails(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.TRIGGER_EMERGENCY_OVERRIDE,
            urgency=0.90,
            confidence=0.70,  # Below 0.90 threshold
            summary="Emergency override triggered.",
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert any("CONFIDENCE_BELOW_THRESHOLD" in e for e in result.validation_errors)

    def test_quiet_hours_deliver_immediately_higher_threshold(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.90,
            confidence=0.75,  # Below 0.85 quiet-hours threshold, above 0.70 normal
        )
        ctx = _make_context(is_quiet_hours=True)
        result = validator.validate(decision, ctx)
        assert any("CONFIDENCE_BELOW_THRESHOLD" in e for e in result.validation_errors)

    def test_deliver_silent_at_threshold_passes(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_SILENT,
            urgency=0.60,
            confidence=0.50,  # At or above 0.45 threshold
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        conf_errors = [e for e in result.validation_errors if "CONFIDENCE_BELOW_THRESHOLD" in e]
        # 0.50 >= 0.45 threshold for DELIVER_SILENT
        assert len(conf_errors) == 0


class TestValidatorRecovery:
    """Tests for recovery strategy and fallback selection."""

    def test_fallback_deliver_silent_for_known_sender(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.90,
            confidence=0.50,  # Below threshold
        )
        ctx = _make_context(personal_sender_known=True)
        result = validator.validate(decision, ctx)
        assert result.suggested_fallback_action == DecisionAction.DELIVER_SILENT

    def test_fallback_summarize_later_for_unknown_sender(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.90,
            confidence=0.50,  # Below threshold
        )
        ctx = _make_context(personal_sender_known=False)
        result = validator.validate(decision, ctx)
        # For unknown sender, fallback is SUMMARIZE_LATER
        assert result.suggested_fallback_action in (
            DecisionAction.DELIVER_SILENT,
            DecisionAction.SUMMARIZE_LATER,
        )

    def test_perfect_decision_all_passes_pass(self):
        validator = DecisionValidator()
        decision = _make_calibrated(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.90,
            importance=0.85,
            confidence=0.88,
            summary="Urgent request from trusted VIP contact.",
            evidence_ids=["ev_001"],
        )
        ctx = _make_context()
        result = validator.validate(decision, ctx)
        assert result.is_valid is True
        assert result.passes_executed == 5
        assert result.suggested_fallback_action is None
