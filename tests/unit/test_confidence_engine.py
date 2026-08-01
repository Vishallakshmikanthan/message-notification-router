"""Unit tests for ConfidenceEngine — calibration, adjustment matrix, and threshold enforcement.

Tests cover:
- Signal agreement adjustment (S_adj).
- Evidence relevance adjustment (E_adj).
- History adjustment (H_adj).
- Temperature-scaled sigmoid calibration.
- Action-specific minimum threshold enforcement.
- Rule-based override (confidence = 1.0).
- Fallback CalibratedDecision for degenerate inputs.
"""

from __future__ import annotations

import math
import pytest
from unittest.mock import MagicMock, patch

from router.application.decision.confidence_engine import ConfidenceEngine
from router.domain.entities.decision_models import (
    CalibratedDecision,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    ReasoningOutput,
    RuleEvaluationResult,
)
from router.domain.entities.evidence import EvidenceBundle, EvidenceItem


def _mock_signal_bundle(
    urgency: float = 0.5,
    trust: float = 0.5,
    spam: float = 0.1,
    relationship: float = 0.5,
    known_contact: float = 0.5,
    is_quiet_hours: bool = False,
    hist_open: float = 0.5,
    hist_reply: float = 0.5,
    business_trust: float = 0.5,
    notification_fatigue: float = 0.2,
):
    sb = MagicMock()
    sb.urgency_score = urgency
    sb.trust.relationship_score.score = relationship
    sb.trust.known_contact_score.score = known_contact
    sb.trust.business_trust_score.score = business_trust
    sb.risk.spam.score = spam
    sb.risk.scam.score = 0.0
    sb.risk.fraud_indicator.score = 0.0
    sb.is_quiet_hours = is_quiet_hours
    sb.personal_sender_known = known_contact > 0.0
    sb.history.historical_open_rate.score = hist_open
    sb.history.historical_reply_rate.score = hist_reply
    sb.behaviour.notification_fatigue.score = notification_fatigue
    sb.candidate_evidence_ids = ["ev_001", "ev_002"]
    return sb


def _mock_evidence_bundle(items=None, evidence_count=3):
    eb = MagicMock(spec=EvidenceBundle)
    eb.evidence_count = evidence_count
    eb.items = items or []
    return eb


def _mock_evidence_item(similarity_score: float = 0.7) -> EvidenceItem:
    return EvidenceItem(
        message_id="ev_001",
        similarity_score=similarity_score,
        behaviour_match=0.5,
        sender_match=0.5,
        business_match=0.5,
        group_match=0.5,
        recency_days=1.0,
        importance_weight=1.0,
        trust_score=0.7,
        reason_retrieved="TEST",
    )


def _mock_context(sb, eb) -> DecisionContext:
    ctx = MagicMock(spec=DecisionContext)
    ctx.context_id = "ctx-001"
    ctx.signal_bundle = sb
    ctx.evidence_bundle = eb
    return ctx


class TestConfidenceEngineInit:
    def test_default_temperature(self):
        engine = ConfidenceEngine()
        assert engine._temperature == 1.40

    def test_custom_temperature(self):
        engine = ConfidenceEngine(temperature=1.20)
        assert engine._temperature == 1.20


class TestSignalAgreementAdjustment:
    """Tests for _compute_signal_agreement."""

    def test_high_agreement_returns_positive_adj(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(urgency=0.7, trust=0.8, spam=0.1)
        adj = engine._compute_signal_agreement(sb)
        assert adj >= 0.0  # High agreement should be positive or neutral

    def test_severe_contradiction_urgency_low_trust(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(urgency=0.90, trust=0.20, spam=0.10)
        # Manually set the nested attribute that _compute_signal_agreement reads
        sb.trust.relationship_score.score = 0.20
        adj = engine._compute_signal_agreement(sb)
        assert adj <= -0.20  # Severe contradiction

    def test_spam_high_vip_contradiction(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(spam=0.80, trust=0.95, relationship=0.95)
        sb.trust.relationship_score.score = 0.95
        adj = engine._compute_signal_agreement(sb)
        # Spam > 0.70 AND trust >= 0.85 → contradiction: -0.20 to -0.40
        assert adj <= -0.20


class TestEvidenceAdjustment:
    """Tests for _compute_evidence_adjustment."""

    def test_no_evidence_returns_max_penalty(self):
        engine = ConfidenceEngine()
        eb = _mock_evidence_bundle(items=[], evidence_count=0)
        adj = engine._compute_evidence_adjustment(eb)
        assert adj == -0.30

    def test_low_relevance_evidence_penalty(self):
        engine = ConfidenceEngine()
        eb = _mock_evidence_bundle(
            items=[_mock_evidence_item(0.15)], evidence_count=1
        )
        adj = engine._compute_evidence_adjustment(eb)
        assert adj == -0.30  # < 0.20 threshold

    def test_medium_relevance_mild_penalty(self):
        engine = ConfidenceEngine()
        eb = _mock_evidence_bundle(
            items=[_mock_evidence_item(0.30)], evidence_count=1
        )
        adj = engine._compute_evidence_adjustment(eb)
        assert adj == -0.15  # 0.20 <= x < 0.40

    def test_good_evidence_no_penalty(self):
        engine = ConfidenceEngine()
        eb = _mock_evidence_bundle(
            items=[_mock_evidence_item(0.75)], evidence_count=1
        )
        adj = engine._compute_evidence_adjustment(eb)
        assert adj == 0.0


class TestHistoryAdjustment:
    """Tests for _compute_history_adjustment."""

    def test_cold_start_no_history_penalty(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(hist_open=0.0, hist_reply=0.0)
        eb = _mock_evidence_bundle()
        ctx = _mock_context(sb, eb)
        adj = engine._compute_history_adjustment(ctx)
        assert adj == -0.10

    def test_has_history_no_penalty(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(hist_open=0.5, hist_reply=0.3)
        eb = _mock_evidence_bundle()
        ctx = _mock_context(sb, eb)
        adj = engine._compute_history_adjustment(ctx)
        assert adj == 0.0


class TestSigmoidCalibration:
    """Tests for _sigmoid_calibrate."""

    def test_high_base_scores_lowered_by_calibration(self):
        engine = ConfidenceEngine(temperature=1.40)
        # Raw score 0.95 should be calibrated DOWN
        calibrated = engine._sigmoid_calibrate(0.95)
        assert calibrated < 0.95

    def test_moderate_scores_maintained(self):
        engine = ConfidenceEngine(temperature=1.40)
        calibrated = engine._sigmoid_calibrate(0.75)
        # Should remain in reasonable range
        assert 0.50 <= calibrated <= 0.90

    def test_clamps_avoid_singularity(self):
        engine = ConfidenceEngine()
        # 0.0 and 1.0 exact values are clamped before logit
        c_near_zero = engine._sigmoid_calibrate(0.001)
        c_near_one = engine._sigmoid_calibrate(0.999)
        assert 0.0 < c_near_zero < 1.0
        assert 0.0 < c_near_one < 1.0

    def test_monotonicity(self):
        """Higher inputs should produce higher (or equal) calibrated outputs."""
        engine = ConfidenceEngine()
        prev = 0.0
        for score in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            calibrated = engine._sigmoid_calibrate(score)
            assert calibrated >= prev
            prev = calibrated


class TestCalibrateRulePath:
    """Tests for calibrate() with rule-based decisions."""

    def test_rule_override_confidence_is_1_0(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(urgency=0.0, trust=0.5, hist_open=0.5, hist_reply=0.5)
        eb = _mock_evidence_bundle(items=[_mock_evidence_item(0.7)])
        ctx = _mock_context(sb, eb)

        rule_result = RuleEvaluationResult(
            rule_fired=True,
            rule_id="RULE_OTP_BYPASS_001",
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            priority=100,
            bypass_llm=True,
            confidence=1.0,
            reasoning_summary="OTP bypass.",
        )

        calibrated = engine.calibrate(
            rule_result=rule_result,
            reasoning_output=None,
            context=ctx,
        )

        assert isinstance(calibrated, CalibratedDecision)
        assert calibrated.bypassed_llm is True
        assert calibrated.triggered_rule_id == "RULE_OTP_BYPASS_001"
        # C_raw=1.0 with good evidence → calibrated confidence should be reasonable
        assert calibrated.calibrated_confidence >= 0.50


class TestCalibrateLLMPath:
    """Tests for calibrate() with LLM reasoning output."""

    def _make_reasoning(
        self,
        action=DecisionAction.DELIVER_IMMEDIATELY,
        urgency=0.85,
        importance=0.80,
        confidence=0.82,
    ) -> ReasoningOutput:
        return ReasoningOutput(
            proposed_action=action,
            urgency_rating=urgency,
            importance_rating=importance,
            reasoning_summary="High urgency from VIP.",
            key_factors=["VIP_CONTACT"],
            raw_confidence=confidence,
        )

    def test_llm_path_calibrates_confidence(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(urgency=0.85, trust=0.80, spam=0.05)
        eb = _mock_evidence_bundle(items=[_mock_evidence_item(0.75)])
        ctx = _mock_context(sb, eb)

        calibrated = engine.calibrate(
            rule_result=None,
            reasoning_output=self._make_reasoning(),
            context=ctx,
        )

        assert isinstance(calibrated, CalibratedDecision)
        assert calibrated.bypassed_llm is False
        assert 0.0 < calibrated.calibrated_confidence < 1.0

    def test_low_confidence_triggers_fallback_action(self):
        """DELIVER_IMMEDIATELY with very low confidence should be downgraded."""
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(urgency=0.50, trust=0.30, spam=0.60, hist_open=0.0, hist_reply=0.0)
        eb = _mock_evidence_bundle(items=[], evidence_count=0)
        ctx = _mock_context(sb, eb)

        reasoning = self._make_reasoning(
            action=DecisionAction.DELIVER_IMMEDIATELY,
            urgency=0.50,
            confidence=0.55,
        )

        calibrated = engine.calibrate(
            rule_result=None,
            reasoning_output=reasoning,
            context=ctx,
        )

        # After severe penalties: 0.55 - 0.40(disagree) - 0.30(no evidence) - 0.10(no history)
        # C_base ≈ -0.25 → floored to 0.05 → calibrated ~0.49 → DELIVER_IMMEDIATELY requires 0.70
        # → should be downgraded
        assert calibrated.action != DecisionAction.DELIVER_IMMEDIATELY


class TestFallbackBehavior:
    """Tests for fallback CalibratedDecision generation."""

    def test_no_rule_no_reasoning_triggers_fallback(self):
        engine = ConfidenceEngine()
        sb = _mock_signal_bundle(known_contact=0.7)
        eb = _mock_evidence_bundle()
        ctx = _mock_context(sb, eb)

        calibrated = engine.calibrate(
            rule_result=None,
            reasoning_output=None,
            context=ctx,
        )

        assert isinstance(calibrated, CalibratedDecision)
        assert calibrated.calibrated_confidence == 0.50
        assert calibrated.action in (
            DecisionAction.DELIVER_SILENT,
            DecisionAction.SUMMARIZE_LATER,
        )
