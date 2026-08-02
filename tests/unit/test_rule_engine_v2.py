"""Unit tests for RuleEngineV2 — full deterministic rule catalog.

Tests cover:
- Level 0 rules (Safety, Emergency, OTP).
- Level 1 rules (Quiet Hours, Group Mute, Business Transactional, VIP).
- Short-circuit mechanics (first-matching rule wins).
- No-rule-fired passthrough.
- Priority ordering guarantees.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from router.application.decision.rule_engine_v2 import RuleEngineV2
from router.domain.entities.decision_models import (
    DecisionAction,
    DecisionContext,
)
from router.domain.entities.evidence import EvidenceBundle


def _make_signal_bundle(
    scam_score: float = 0.0,
    spam_score: float = 0.0,
    emergency_score: float = 0.0,
    urgency_score: float = 0.0,
    trust_score: float = 0.5,
    relationship_score: float = 0.5,
    known_contact: float = 0.5,
    is_quiet_hours: bool = False,
    business_trust: float = 0.5,
    promotional_intent: float = 0.0,
    transactional_intent: float = 0.0,
    forward_chain: float = 0.0,
    is_frequently_forwarded: bool = False,
    is_muted: bool = False,
    direct_mention: float = 0.0,
    fraud_indicator: float = 0.0,
    family_emergency: float = 0.0,
    health_emergency: float = 0.0,
    payment_score: float = 0.0,
    deadline_score: float = 0.0,
    time_sensitive: float = 0.0,
    critical_announcement: float = 0.0,
    unverified: float = 0.0,
):
    """Build a mock SignalBundle with specified field values."""
    sb = MagicMock()

    # Urgency
    sb.urgency.emergency.score = emergency_score
    sb.urgency.family_emergency.score = family_emergency
    sb.urgency.health_emergency.score = health_emergency
    sb.urgency.payment.score = payment_score
    sb.urgency.deadline.score = deadline_score
    sb.urgency.time_sensitive_event.score = time_sensitive
    sb.urgency.critical_announcement.score = critical_announcement

    # Risk
    sb.risk.scam.score = scam_score
    sb.risk.spam.score = spam_score
    sb.risk.fraud_indicator.score = fraud_indicator
    sb.risk.forward_chain_risk.score = forward_chain

    # Trust
    sb.trust.relationship_score.score = relationship_score
    sb.trust.business_trust_score.score = business_trust
    sb.trust.known_contact_score.score = known_contact

    # Business
    sb.business.promotional_intent.score = promotional_intent
    sb.business.transactional_intent.score = transactional_intent

    # Group
    sb.group.direct_mention.score = direct_mention

    # Behaviour
    sb.behaviour.notification_fatigue.score = 0.0

    # Derived properties
    sb.urgency_score = max(emergency_score, urgency_score, payment_score, time_sensitive)
    sb.is_quiet_hours = is_quiet_hours
    sb.personal_sender_known = known_contact > 0.0
    sb.group_is_muted_by_user = is_muted
    sb.unverified_business_flag = unverified >= 0.5

    return sb


def _make_context(
    sb,
    is_group: bool = False,
    contains_links: bool = False,
    is_forwarded: bool = False,
    is_frequently_forwarded: bool = False,
) -> DecisionContext:
    """Build a DecisionContext wrapping the given mock signal bundle."""
    mc = MagicMock()
    mc.core_message.message_id = "msg_test"
    mc.message_id = "msg_test"
    mc.core_message.is_forwarded = is_forwarded
    mc.core_message.is_frequently_forwarded = is_frequently_forwarded
    mc.core_message.contains_links = contains_links
    mc.core_message.char_count = 100
    mc.conversation.is_group_chat = is_group

    eb = EvidenceBundle(
        query_message_id="msg_test",
        user_id="user_001",
        retrieval_confidence=0.0,
        evidence_count=0,
    )

    ctx = MagicMock(spec=DecisionContext)
    ctx.context_id = "ctx-test-001"
    ctx.message_context = mc
    ctx.signal_bundle = sb
    ctx.evidence_bundle = eb

    return ctx


class TestRuleEngineV2Init:
    """Tests for RuleEngineV2 initialization."""

    def test_rules_registered(self):
        engine = RuleEngineV2()
        assert len(engine._rules) > 10, "Expected at least 10 rules registered."

    def test_rules_sorted_by_priority_descending(self):
        engine = RuleEngineV2()
        priorities = [r.priority for r in engine._rules]
        assert priorities == sorted(priorities, reverse=True)


class TestLevel0SafetyRules:
    """Tests for Level 0 safety and emergency rules (Priority 100)."""

    def test_high_scam_score_fires_suppress_spam(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(scam_score=0.96)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.bypass_llm is True
        assert result.action == DecisionAction.SUPPRESS_SPAM
        # RULE_SAFETY_THREAT_001 (priority 100) may fire before RULE_HIGH_SCAM_SCORE_001 (95)
        assert result.priority in (95, 100)

    def test_emergency_keyword_with_known_contact_fires_override(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(emergency_score=0.90, known_contact=0.8)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.TRIGGER_EMERGENCY_OVERRIDE
        assert result.priority == 100

    def test_family_emergency_fires_override(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(family_emergency=0.85, relationship_score=0.80)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.TRIGGER_EMERGENCY_OVERRIDE

    def test_health_emergency_fires_override(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(health_emergency=0.85)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.TRIGGER_EMERGENCY_OVERRIDE


class TestLevel1QuietHoursRules:
    """Tests for Level 1 quiet hours rules."""

    def test_non_vip_quiet_hours_deliver_silent(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(
            is_quiet_hours=True,
            relationship_score=0.50,  # non-VIP
            urgency_score=0.40,
        )
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.DELIVER_SILENT
        assert result.bypass_llm is True

    def test_vip_quiet_hours_urgent_bypass(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(
            is_quiet_hours=True,
            relationship_score=0.90,  # VIP
            urgency_score=0.80,
        )
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.DELIVER_IMMEDIATELY
        assert result.bypass_llm is True


class TestLevel1GroupMuteRule:
    """Tests for group mute rule."""

    def test_muted_group_no_mention_suppress(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(is_muted=True, direct_mention=0.0)
        ctx = _make_context(sb, is_group=True)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.SUPPRESS_MUTE
        assert result.bypass_llm is True

    def test_muted_group_with_mention_pass_through(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(is_muted=True, direct_mention=0.9)
        ctx = _make_context(sb, is_group=True)

        # This rule should NOT fire (mention overrides mute suppression)
        result = engine.evaluate(ctx)

        # Either another rule fires or no rule fires — but NOT SUPPRESS_MUTE
        if result.rule_fired:
            assert result.action != DecisionAction.SUPPRESS_MUTE


class TestBusinessRules:
    """Tests for business transactional and promotional rules."""

    def test_verified_transactional_deliver_silent(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(business_trust=0.85, transactional_intent=0.85)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.DELIVER_SILENT
        assert result.bypass_llm is True

    def test_unverified_promotional_batch_digest(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(unverified=1.0, promotional_intent=0.75)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.BATCH_DIGEST

    def test_payment_reminder_deliver_immediately(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(payment_score=0.85, deadline_score=0.80)
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.DELIVER_IMMEDIATELY


class TestNoRuleFired:
    """Tests for pass-through (no rule matched)."""

    def test_normal_message_no_rule_fires(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle()  # All zeros / defaults
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is False
        assert result.bypass_llm is False
        assert result.confidence == 0.0
        assert result.action is None

    def test_low_risk_personal_message_no_rule(self):
        engine = RuleEngineV2()
        sb = _make_signal_bundle(
            known_contact=0.7,
            trust_score=0.75,
            scam_score=0.05,
            spam_score=0.10,
        )
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is False
        assert result.bypass_llm is False


class TestPriorityOrdering:
    """Tests verifying priority ordering: higher-priority rules win."""

    def test_high_scam_beats_vip_bypass(self):
        """Even if trust is high, a scam score of 0.96 must fire SUPPRESS_SPAM."""
        engine = RuleEngineV2()
        sb = _make_signal_bundle(
            scam_score=0.96,
            relationship_score=0.90,
            is_quiet_hours=True,
        )
        ctx = _make_context(sb)

        result = engine.evaluate(ctx)

        assert result.rule_fired is True
        assert result.action == DecisionAction.SUPPRESS_SPAM

    def test_rule_confidence_values(self):
        """Level 0 rules must have confidence == 1.0, Level 1 rules == 0.90-0.95."""
        engine = RuleEngineV2()
        for rule in engine._rules:
            if rule.priority == 100:
                assert rule.confidence == 1.0, f"Level 0 rule {rule.rule_id} has confidence != 1.0"
            elif rule.priority >= 80:
                assert rule.confidence >= 0.90, f"Level 1 rule {rule.rule_id} has confidence < 0.90"
