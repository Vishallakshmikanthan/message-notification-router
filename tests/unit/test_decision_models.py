"""Unit tests for decision_models.py — Phase 7 Decision Data Models."""

from __future__ import annotations

import pytest
from router.domain.entities.decision_models import (
    ActionParameters,
    CalibratedDecision,
    ConfidenceBreakdown,
    DecisionAction,
    DecisionCategory,
    DecisionMetadata,
    DecisionResult,
    LatencyBreakdown,
    ReasonerInputFrame,
    ReasoningOutput,
    RuleEvaluationResult,
    VerificationStatus,
    build_action_params,
)


class TestDecisionAction:
    """Tests for DecisionAction enum."""

    def test_all_actions_are_strings(self):
        for action in DecisionAction:
            assert isinstance(str(action), str)

    def test_action_values(self):
        assert str(DecisionAction.DELIVER_IMMEDIATELY) == "DELIVER_IMMEDIATELY"
        assert str(DecisionAction.SUPPRESS_SPAM) == "SUPPRESS_SPAM"
        assert str(DecisionAction.TRIGGER_EMERGENCY_OVERRIDE) == "TRIGGER_EMERGENCY_OVERRIDE"

    def test_action_count(self):
        assert len(DecisionAction) == 7


class TestDecisionCategory:
    """Tests for DecisionCategory enum."""

    def test_category_count(self):
        assert len(DecisionCategory) == 8

    def test_category_values(self):
        assert str(DecisionCategory.SPAM_VIRAL) == "SPAM_VIRAL"
        assert str(DecisionCategory.TRANSACTIONAL) == "TRANSACTIONAL"


class TestRuleEvaluationResult:
    """Tests for RuleEvaluationResult dataclass."""

    def test_rule_fired_true(self):
        result = RuleEvaluationResult(
            rule_fired=True,
            rule_id="RULE_OTP_BYPASS_001",
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            priority=100,
            bypass_llm=True,
            confidence=1.0,
            reasoning_summary="OTP bypass rule fired.",
        )
        assert result.rule_fired is True
        assert result.bypass_llm is True
        assert result.confidence == 1.0
        assert result.priority == 100

    def test_no_rule_fired(self):
        result = RuleEvaluationResult(rule_fired=False, bypass_llm=False, confidence=0.0)
        assert result.rule_fired is False
        assert result.bypass_llm is False
        assert result.rule_id is None
        assert result.action is None

    def test_immutability(self):
        result = RuleEvaluationResult(rule_fired=True, bypass_llm=True, confidence=1.0)
        with pytest.raises((TypeError, AttributeError)):
            result.rule_fired = False  # type: ignore[misc]


class TestReasoningOutput:
    """Tests for ReasoningOutput dataclass."""

    def test_valid_reasoning_output(self):
        output = ReasoningOutput(
            proposed_action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency_rating=0.85,
            importance_rating=0.80,
            reasoning_summary="High urgency detected from VIP contact.",
            key_factors=["VIP_CONTACT", "HIGH_URGENCY"],
            raw_confidence=0.88,
            proposed_category=DecisionCategory.PERSONAL_URGENT,
        )
        assert output.proposed_action == DecisionAction.DELIVER_IMMEDIATELY
        assert output.urgency_rating == 0.85
        assert len(output.key_factors) == 2

    def test_immutability(self):
        output = ReasoningOutput(
            proposed_action=DecisionAction.SUPPRESS_SPAM,
            urgency_rating=0.10,
            importance_rating=0.10,
            reasoning_summary="Spam detected.",
            key_factors=["HIGH_SPAM_SCORE"],
            raw_confidence=0.90,
        )
        with pytest.raises((TypeError, AttributeError)):
            output.raw_confidence = 0.50  # type: ignore[misc]


class TestCalibratedDecision:
    """Tests for CalibratedDecision dataclass."""

    def _make_calibrated(self, action=DecisionAction.DELIVER_IMMEDIATELY) -> CalibratedDecision:
        breakdown = ConfidenceBreakdown(
            raw_llm_confidence=0.82,
            signal_agreement_factor=0.20,
            evidence_relevance_factor=-0.05,
            history_adjustment_factor=0.0,
            calibrated_confidence=0.78,
        )
        return CalibratedDecision(
            action=action,
            category=DecisionCategory.PERSONAL_URGENT,
            urgency_score=0.85,
            importance_score=0.80,
            reasoning_summary="Emergency from VIP.",
            key_factors=["VIP_CONTACT"],
            evidence_ids=["msg_001"],
            calibrated_confidence=0.78,
            confidence_breakdown=breakdown,
        )

    def test_calibrated_fields(self):
        cd = self._make_calibrated()
        assert cd.action == DecisionAction.DELIVER_IMMEDIATELY
        assert cd.calibrated_confidence == 0.78
        assert cd.bypassed_llm is False

    def test_immutability(self):
        cd = self._make_calibrated()
        with pytest.raises((TypeError, AttributeError)):
            cd.action = DecisionAction.SUPPRESS_SPAM  # type: ignore[misc]


class TestActionParameters:
    """Tests for ActionParameters and build_action_params."""

    def test_deliver_immediately_params(self):
        params = build_action_params(DecisionAction.DELIVER_IMMEDIATELY)
        assert params.play_sound is True
        assert params.vibrate is True
        assert params.banner_style == "HEADS_UP"

    def test_suppress_spam_params(self):
        params = build_action_params(DecisionAction.SUPPRESS_SPAM)
        assert params.play_sound is False
        assert params.banner_style == "NONE"

    def test_emergency_override_params(self):
        params = build_action_params(DecisionAction.TRIGGER_EMERGENCY_OVERRIDE)
        assert params.priority_level == 10
        assert params.play_sound is True

    def test_batch_digest_with_schedule(self):
        params = build_action_params(
            DecisionAction.BATCH_DIGEST, scheduled_time="2026-08-02T08:00:00Z"
        )
        assert params.scheduled_time == "2026-08-02T08:00:00Z"

    def test_deliver_immediately_no_schedule(self):
        params = build_action_params(
            DecisionAction.DELIVER_IMMEDIATELY, scheduled_time="2026-08-02T08:00:00Z"
        )
        # scheduled_time should NOT be injected for DELIVER_IMMEDIATELY
        assert params.scheduled_time is None


class TestDecisionResultAuditHash:
    """Tests for DecisionResult audit hash generation."""

    def _make_result(self) -> DecisionResult:
        breakdown = ConfidenceBreakdown(calibrated_confidence=0.78)
        metadata = DecisionMetadata(
            execution_id="test-exec-id",
            confidence_breakdown=breakdown,
        )
        return DecisionResult(
            decision_id="dec-001",
            context_id="ctx-001",
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency_score=0.85,
            importance_score=0.80,
            category=DecisionCategory.PERSONAL_URGENT,
            reasoning_summary="VIP contact urgent message.",
            triggered_rule_id=None,
            bypassed_llm=False,
            action_params=ActionParameters(),
            metadata=metadata,
            evidence_ids=["msg_001"],
        )

    def test_audit_hash_generated(self):
        result = self._make_result()
        audit_hash = result.compute_audit_hash()
        assert len(audit_hash) == 64  # SHA-256 hex digest
        assert audit_hash.isalnum()

    def test_audit_hash_deterministic(self):
        result = self._make_result()
        assert result.compute_audit_hash() == result.compute_audit_hash()
