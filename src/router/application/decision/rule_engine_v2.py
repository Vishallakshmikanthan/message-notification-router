"""RuleEngineV2 — Full deterministic rule catalog as specified in rule_engine.md.

Implements all Level 0 (Priority 100, Safety) and Level 1 (Priority 80-99,
User/Business) rules with short-circuit evaluation and LLM bypass semantics.

Key design:
- Rules are registered with a priority score (0–100).
- Evaluation iterates in descending priority order (highest first).
- First matching rule short-circuits all further evaluation.
- Rule evaluation NEVER mutates DecisionContext or any persistent state.
- Zero LLM dependency: pure boolean logic over signal/context fields.

Spec: rule_engine.md §2 LLM Bypass Matrix, §3 Rule Catalog.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    RuleEvaluationResult,
)
from router.domain.ports.decision_ports import IRuleEngineV2

logger = get_logger(__name__)


@dataclass
class _Rule:
    """Internal rule registration record.

    Attributes:
        rule_id: Unique identifier string (e.g., 'RULE_OTP_BYPASS_001').
        description: Human-readable description for audit logs.
        priority: Integer 0–100; higher = evaluated first.
        action: DecisionAction to return if rule matches.
        category: DecisionCategory to classify the message.
        bypass_llm: Whether this rule bypasses LLM evaluation.
        confidence: Decision confidence level (0.95–1.0 for hard rules).
        condition: Callable that returns True if this rule fires.
    """

    rule_id: str
    description: str
    priority: int
    action: DecisionAction
    category: DecisionCategory
    bypass_llm: bool
    confidence: float
    condition: Callable[[DecisionContext], bool]


class RuleEngineV2(IRuleEngineV2):
    """Full deterministic rule engine implementing all Level 0 and Level 1 rules.

    Evaluates rules in strict descending priority order with short-circuit
    semantics: the first matching rule returns immediately without evaluating
    lower-priority rules.

    Thread-safe: the rule registry is built once at construction and is
    immutable thereafter. No shared mutable state.
    """

    def __init__(self) -> None:
        """Initialize and register all rules sorted by priority (DESC)."""
        self._rules: list[_Rule] = []
        self._register_all_rules()
        self._rules.sort(key=lambda r: (-r.priority, r.rule_id))
        logger.info(
            "RuleEngineV2 initialized",
            total_rules=len(self._rules),
        )

    def evaluate(self, context: DecisionContext) -> RuleEvaluationResult:
        """Evaluate the full deterministic rule catalog against the DecisionContext.

        Iterates rules in descending priority order. Returns on first match.
        If no rule fires, returns RuleEvaluationResult(rule_fired=False, bypass_llm=False).

        Args:
            context: Validated DecisionContext.

        Returns:
            RuleEvaluationResult indicating whether a rule fired and bypass_llm status.
        """
        start_time = time.perf_counter()
        message_id = (
            context.message_context.message_id
            or context.message_context.core_message.message_id
        )

        for rule in self._rules:
            try:
                if rule.condition(context):
                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    logger.info(
                        "Rule fired",
                        rule_id=rule.rule_id,
                        action=rule.action,
                        priority=rule.priority,
                        bypass_llm=rule.bypass_llm,
                        message_id=message_id,
                        rule_engine_ms=round(latency_ms, 2),
                    )
                    return RuleEvaluationResult(
                        rule_fired=True,
                        rule_id=rule.rule_id,
                        action=rule.action,
                        category=rule.category,
                        priority=rule.priority,
                        bypass_llm=rule.bypass_llm,
                        confidence=rule.confidence,
                        reasoning_summary=rule.description,
                    )
            except Exception as exc:
                # Individual rule failures MUST NOT crash the engine.
                logger.error(
                    "Rule evaluation error",
                    rule_id=rule.rule_id,
                    error=str(exc),
                    message_id=message_id,
                )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "No deterministic rule matched; routing to LLM path",
            message_id=message_id,
            rules_evaluated=len(self._rules),
            rule_engine_ms=round(latency_ms, 2),
        )
        return RuleEvaluationResult(
            rule_fired=False,
            bypass_llm=False,
            confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def _register_all_rules(self) -> None:
        """Register all rule catalog entries from rule_engine.md §3."""
        # ---- Level 0: Safety Overrides (Priority 100) ----------------
        self._register(
            rule_id="RULE_SAFETY_THREAT_001",
            description="Threat or harassment detected: immediate safety suppress.",
            priority=100,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SAFETY_SECURITY,
            bypass_llm=True,
            confidence=1.0,
            condition=lambda ctx: (
                ctx.signal_bundle.risk.scam.score > 0.85
                or ctx.message_context.core_message.is_forwarded  # used as proxy for harassment_flag
                and ctx.signal_bundle.risk.spam.score > 0.85
            ),
        )
        self._register(
            rule_id="RULE_OTP_BYPASS_001",
            description="Verified 2FA/OTP code: deliver immediately without LLM.",
            priority=100,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            bypass_llm=True,
            confidence=1.0,
            condition=lambda ctx: (
                # OTP detection: short message with numeric pattern + high trust
                ctx.signal_bundle.trust.business_trust_score.score > 0.8
                and ctx.signal_bundle.urgency.payment.score > 0.6
                and ctx.message_context.core_message.char_count <= 200
            ),
        )
        self._register(
            rule_id="RULE_EMERGENCY_KEYWORD_001",
            description="Emergency keyword from known contact: trigger override.",
            priority=100,
            action=DecisionAction.TRIGGER_EMERGENCY_OVERRIDE,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=1.0,
            condition=lambda ctx: ctx.signal_bundle.urgency.emergency.score >= 0.85,
        )
        self._register(
            rule_id="RULE_FAMILY_EMERGENCY_001",
            description="Family emergency signal from VIP contact.",
            priority=100,
            action=DecisionAction.TRIGGER_EMERGENCY_OVERRIDE,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=1.0,
            condition=lambda ctx: (
                ctx.signal_bundle.urgency.family_emergency.score > 0.80
                and ctx.signal_bundle.trust.relationship_score.score >= 0.75
            ),
        )
        self._register(
            rule_id="RULE_HEALTH_EMERGENCY_001",
            description="Health emergency signal detected.",
            priority=100,
            action=DecisionAction.TRIGGER_EMERGENCY_OVERRIDE,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=1.0,
            condition=lambda ctx: ctx.signal_bundle.urgency.health_emergency.score > 0.80,
        )

        # ---- Level 0 / 1: Spam & Scam Rules (Priority 95) ------------
        self._register(
            rule_id="RULE_SPAM_BROADCAST_001",
            description="Unsolicited broadcast from unknown sender with high spam score.",
            priority=95,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SPAM_VIRAL,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: (
                not ctx.signal_bundle.personal_sender_known
                and ctx.message_context.core_message.is_forwarded
                and ctx.signal_bundle.risk.spam.score > 0.70
            ),
        )
        self._register(
            rule_id="RULE_PHISHING_LINK_001",
            description="Phishing link pattern from unknown sender.",
            priority=95,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SAFETY_SECURITY,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: (
                not ctx.signal_bundle.personal_sender_known
                and ctx.message_context.core_message.contains_links
                and ctx.signal_bundle.risk.fraud_indicator.score > 0.75
            ),
        )
        self._register(
            rule_id="RULE_HIGH_SCAM_SCORE_001",
            description="Scam probability exceeds critical threshold.",
            priority=95,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SPAM_VIRAL,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: ctx.signal_bundle.risk.scam.score >= 0.85,
        )
        self._register(
            rule_id="RULE_HEALTH_LAB_RESULTS_001",
            description="Hospital or medical lab report alert: deliver immediately.",
            priority=95,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: any(
                kw in (
                    (ctx.message_context.core_message and ctx.message_context.core_message.cleaned_text)
                    or ctx.message_context.message_text
                    or ""
                ).lower()
                for kw in ["hospital", "lab result", "doctor alert", "prescription ready", "clinic alert", "patient alert"]
            ),
        )
        self._register(
            rule_id="RULE_CHAIN_SPAM_001",
            description="Broadcast viral spam or chain letter detected.",
            priority=95,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.SPAM_VIRAL,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: any(
                kw in (
                    (ctx.message_context.core_message and ctx.message_context.core_message.cleaned_text)
                    or ctx.message_context.message_text
                    or ""
                ).lower()
                for kw in ["forward this to", "forward to 10", "chain letter", "unsolicited broadcast", "forward this message"]
            ),
        )
        self._register(
            rule_id="RULE_EXPLICIT_GROUP_MUTE_001",
            description="Group is explicitly muted by user and user is not mentioned.",
            priority=95,
            action=DecisionAction.SUPPRESS_MUTE,
            category=DecisionCategory.WORK_ROUTINE,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: (
                ctx.message_context.conversation.is_group_chat
                and ctx.signal_bundle.group_is_muted_by_user
                and ctx.signal_bundle.group.direct_mention.score < 0.5
            ),
        )

        # ---- Level 1: Quiet Hours Rules (Priority 90) ----------------
        self._register(
            rule_id="RULE_QUIET_HOURS_NON_VIP_001",
            description="Quiet hours active; non-VIP sender; urgency below threshold.",
            priority=90,
            action=DecisionAction.DELIVER_SILENT,
            category=DecisionCategory.PERSONAL_CASUAL,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: (
                ctx.signal_bundle.is_quiet_hours
                and ctx.signal_bundle.risk.spam.score <= 0.50
                and ctx.signal_bundle.risk.scam.score <= 0.50
                and ctx.signal_bundle.trust.relationship_score.score < 0.85
                and ctx.signal_bundle.urgency_score < 0.85
            ),
        )
        self._register(
            rule_id="RULE_VIP_QUIET_HOUR_BYPASS_001",
            description="VIP contact bypasses quiet hours during urgent message.",
            priority=90,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: (
                ctx.signal_bundle.is_quiet_hours
                and ctx.signal_bundle.trust.relationship_score.score >= 0.85
                and ctx.signal_bundle.urgency_score >= 0.75
            ),
        )
        self._register(
            rule_id="RULE_TRAVEL_ALERT_001",
            description="Flight/travel schedule alert with high urgency.",
            priority=90,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.signal_bundle.urgency.critical_announcement.score > 0.70
                and ctx.signal_bundle.trust.business_trust_score.score > 0.70
                and ctx.signal_bundle.urgency.time_sensitive_event.score > 0.70
            ),
        )

        # ---- Level 1: Business & Transactional Rules (Priority 80-85) ----
        self._register(
            rule_id="RULE_VIRAL_FORWARD_001",
            description="Viral forwarded message from non-VIP: batch digest.",
            priority=85,
            action=DecisionAction.BATCH_DIGEST,
            category=DecisionCategory.SPAM_VIRAL,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.message_context.core_message.is_frequently_forwarded
                and not ctx.signal_bundle.trust.relationship_score.score >= 0.85
            ),
        )
        self._register(
            rule_id="RULE_FLIGHT_DEPARTURE_001",
            description="Flight departure or gate change notification: deliver immediately.",
            priority=96,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            bypass_llm=True,
            confidence=0.95,
            condition=lambda ctx: ctx.signal_bundle.urgency.time_sensitive_event.score >= 0.85,
        )
        self._register(
            rule_id="RULE_PAYMENT_REMINDER_001",
            description="Impending bill due date or payment reminder: deliver immediately.",
            priority=95,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.TRANSACTIONAL,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.signal_bundle.urgency.payment.score > 0.80
                and ctx.signal_bundle.risk.scam.score < 0.60
            ),
        )
        self._register(
            rule_id="RULE_REPEAT_PROMO_001",
            description="Repeated vendor promotions exceeding daily threshold.",
            priority=85,
            action=DecisionAction.SUPPRESS_SPAM,
            category=DecisionCategory.MARKETING_PROMO,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.signal_bundle.business.promotional_intent.score > 0.80
                and ctx.signal_bundle.risk.spam.score > 0.60
            ),
        )
        self._register(
            rule_id="RULE_VERIFIED_TRANSACTIONAL_001",
            description="Verified business transactional message: deliver silently.",
            priority=80,
            action=DecisionAction.DELIVER_SILENT,
            category=DecisionCategory.TRANSACTIONAL,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.signal_bundle.trust.business_trust_score.score > 0.75
                and ctx.signal_bundle.business.transactional_intent.score > 0.75
            ),
        )
        self._register(
            rule_id="RULE_UNVERIFIED_PROMO_001",
            description="Unverified business promotional message: batch digest.",
            priority=80,
            action=DecisionAction.BATCH_DIGEST,
            category=DecisionCategory.MARKETING_PROMO,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                ctx.signal_bundle.unverified_business_flag
                and ctx.signal_bundle.business.promotional_intent.score > 0.60
            ),
        )
        self._register(
            rule_id="RULE_VIP_DIRECT_001",
            description="Direct one-on-one message from VIP contact (non-quiet hours).",
            priority=80,
            action=DecisionAction.DELIVER_IMMEDIATELY,
            category=DecisionCategory.PERSONAL_URGENT,
            bypass_llm=True,
            confidence=0.90,
            condition=lambda ctx: (
                not ctx.message_context.conversation.is_group_chat
                and ctx.signal_bundle.trust.relationship_score.score >= 0.85
                and not ctx.signal_bundle.is_quiet_hours
            ),
        )

    def _register(
        self,
        rule_id: str,
        description: str,
        priority: int,
        action: DecisionAction,
        category: DecisionCategory,
        bypass_llm: bool,
        confidence: float,
        condition: Callable[[DecisionContext], bool],
    ) -> None:
        """Internal rule registration helper.

        Args:
            rule_id: Unique rule identifier.
            description: Human-readable explanation for audit logs.
            priority: Integer 0–100 (higher = evaluated first).
            action: DecisionAction to assign if rule fires.
            category: DecisionCategory classification.
            bypass_llm: Whether to bypass LLM when this rule fires.
            confidence: Confidence score (0.90–1.0 for hard rules).
            condition: Callable accepting DecisionContext, returning bool.
        """
        self._rules.append(
            _Rule(
                rule_id=rule_id,
                description=description,
                priority=priority,
                action=action,
                category=category,
                bypass_llm=bypass_llm,
                confidence=confidence,
                condition=condition,
            )
        )
