"""SignalFactory implementation for constructing immutable signal objects and default fallbacks."""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from router.domain.entities.signal import (
    BehaviourSignals,
    BusinessSignals,
    ConversationSignals,
    GroupSignals,
    HistorySignals,
    MediaSignals,
    RelationshipSignals,
    RiskSignals,
    SignalBundle,
    SignalBundleMetadata,
    SignalExplainability,
    SignalValue,
    TemporalSignals,
    TrustSignals,
    UrgencySignals,
)


class SignalFactory:
    """Factory for instantiating immutable SignalValue objects, fallbacks, and category containers."""

    @staticmethod
    def create_null_fallback(driver: str = "NONE", rationale: str = "Default Null-Object Imputation due to missing input context.") -> SignalValue:
        """Create standard null object fallback SignalValue with 0.0 score and confidence."""
        return SignalValue(
            score=0.0,
            confidence=0.0,
            explainability=SignalExplainability(
                raw_value=0.0,
                primary_driver=driver,
                rationale=rationale,
                contributing_factors={},
            ),
        )

    @staticmethod
    def create_signal_value(
        score: float,
        confidence: float,
        raw_value: float,
        primary_driver: str,
        rationale: str,
        contributing_factors: Dict[str, float] | None = None,
    ) -> SignalValue:
        """Construct bounded SignalValue ensuring strictly [0.0, 1.0] limits."""
        clamped_score = max(0.0, min(1.0, float(score)))
        clamped_conf = max(0.0, min(1.0, float(confidence)))
        factors = contributing_factors if contributing_factors is not None else {}
        return SignalValue(
            score=clamped_score,
            confidence=clamped_conf,
            explainability=SignalExplainability(
                raw_value=float(raw_value),
                primary_driver=primary_driver,
                rationale=rationale,
                contributing_factors=factors,
            ),
        )

    @classmethod
    def assemble_behaviour_signals(cls, signals: Dict[str, SignalValue]) -> BehaviourSignals:
        """Assemble BehaviourSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return BehaviourSignals(
            notification_fatigue=signals.get("notification_fatigue", f("notification_fatigue")),
            reading_responsiveness=signals.get("reading_responsiveness", f("reading_responsiveness")),
            reply_velocity=signals.get("reply_velocity", f("reply_velocity")),
            dismiss_propensity=signals.get("dismiss_propensity", f("dismiss_propensity")),
            ignore_propensity=signals.get("ignore_propensity", f("ignore_propensity")),
            time_of_day_affinity=signals.get("time_of_day_affinity", f("time_of_day_affinity")),
            weekend_responsiveness=signals.get("weekend_responsiveness", f("weekend_responsiveness")),
            group_engagement=signals.get("group_engagement", f("group_engagement")),
            business_engagement=signals.get("business_engagement", f("business_engagement")),
        )

    @classmethod
    def assemble_risk_signals(cls, signals: Dict[str, SignalValue]) -> RiskSignals:
        """Assemble RiskSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return RiskSignals(
            spam=signals.get("spam", f("spam")),
            scam=signals.get("scam", f("scam")),
            fraud_indicator=signals.get("fraud_indicator", f("fraud_indicator")),
            business_trust=signals.get("business_trust", f("business_trust")),
            forward_chain_risk=signals.get("forward_chain_risk", f("forward_chain_risk")),
            unknown_sender_risk=signals.get("unknown_sender_risk", f("unknown_sender_risk")),
            visual_scam_risk=signals.get("visual_scam_risk", f("visual_scam_risk")),
            voice_scam_risk=signals.get("voice_scam_risk", f("voice_scam_risk")),
        )

    @classmethod
    def assemble_trust_signals(cls, signals: Dict[str, SignalValue]) -> TrustSignals:
        """Assemble TrustSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return TrustSignals(
            business_trust_score=signals.get("business_trust_score", f("business_trust_score")),
            relationship_score=signals.get("relationship_score", f("relationship_score")),
            known_contact_score=signals.get("known_contact_score", f("known_contact_score")),
            group_reliability=signals.get("group_reliability", f("group_reliability")),
            historical_trust=signals.get("historical_trust", f("historical_trust")),
            interaction_strength=signals.get("interaction_strength", f("interaction_strength")),
        )

    @classmethod
    def assemble_urgency_signals(cls, signals: Dict[str, SignalValue]) -> UrgencySignals:
        """Assemble UrgencySignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return UrgencySignals(
            emergency=signals.get("emergency", f("emergency")),
            time_sensitive_event=signals.get("time_sensitive_event", f("time_sensitive_event")),
            payment=signals.get("payment", f("payment")),
            deadline=signals.get("deadline", f("deadline")),
            meeting=signals.get("meeting", f("meeting")),
            appointment=signals.get("appointment", f("appointment")),
            family_emergency=signals.get("family_emergency", f("family_emergency")),
            health_emergency=signals.get("health_emergency", f("health_emergency")),
            critical_announcement=signals.get("critical_announcement", f("critical_announcement")),
        )

    @classmethod
    def assemble_relationship_signals(cls, signals: Dict[str, SignalValue]) -> RelationshipSignals:
        """Assemble RelationshipSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return RelationshipSignals(
            tie_strength=signals.get("tie_strength", f("tie_strength")),
            intimacy_score=signals.get("intimacy_score", f("intimacy_score")),
            reciprocity_ratio=signals.get("reciprocity_ratio", f("reciprocity_ratio")),
        )

    @classmethod
    def assemble_business_signals(cls, signals: Dict[str, SignalValue]) -> BusinessSignals:
        """Assemble BusinessSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return BusinessSignals(
            commercial_intent=signals.get("commercial_intent", f("commercial_intent")),
            transactional_intent=signals.get("transactional_intent", f("transactional_intent")),
            promotional_intent=signals.get("promotional_intent", f("promotional_intent")),
        )

    @classmethod
    def assemble_group_signals(cls, signals: Dict[str, SignalValue]) -> GroupSignals:
        """Assemble GroupSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return GroupSignals(
            group_importance=signals.get("group_importance", f("group_importance")),
            direct_mention=signals.get("direct_mention", f("direct_mention")),
        )

    @classmethod
    def assemble_history_signals(cls, signals: Dict[str, SignalValue]) -> HistorySignals:
        """Assemble HistorySignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return HistorySignals(
            historical_open_rate=signals.get("historical_open_rate", f("historical_open_rate")),
            historical_reply_rate=signals.get("historical_reply_rate", f("historical_reply_rate")),
        )

    @classmethod
    def assemble_temporal_signals(cls, signals: Dict[str, SignalValue]) -> TemporalSignals:
        """Assemble TemporalSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return TemporalSignals(
            quiet_hours_active=signals.get("quiet_hours_active", f("quiet_hours_active")),
        )

    @classmethod
    def assemble_media_signals(cls, signals: Dict[str, SignalValue]) -> MediaSignals:
        """Assemble MediaSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return MediaSignals(
            media_importance=signals.get("media_importance", f("media_importance")),
        )

    @classmethod
    def assemble_conversation_signals(cls, signals: Dict[str, SignalValue]) -> ConversationSignals:
        """Assemble ConversationSignals category container using dict of signal values or fallbacks."""
        f = cls.create_null_fallback
        return ConversationSignals(
            conversation_importance=signals.get("conversation_importance", f("conversation_importance")),
        )

    @classmethod
    def build_bundle(
        cls,
        message_id: str,
        all_signals: Dict[str, SignalValue],
        latency_ms: float,
        global_confidence: float,
        global_completeness: float,
    ) -> SignalBundle:
        """Assemble complete frozen SignalBundle container."""
        metadata = SignalBundleMetadata(
            bundle_id=str(uuid.uuid4()),
            message_id=message_id,
            computed_at=datetime.now(timezone.utc).isoformat(),
            calculation_latency_ms=round(latency_ms, 3),
            global_confidence=round(global_confidence, 4),
            global_completeness=round(global_completeness, 4),
        )
        return SignalBundle(
            metadata=metadata,
            behaviour=cls.assemble_behaviour_signals(all_signals),
            risk=cls.assemble_risk_signals(all_signals),
            trust=cls.assemble_trust_signals(all_signals),
            urgency=cls.assemble_urgency_signals(all_signals),
            relationship=cls.assemble_relationship_signals(all_signals),
            business=cls.assemble_business_signals(all_signals),
            group=cls.assemble_group_signals(all_signals),
            history=cls.assemble_history_signals(all_signals),
            temporal=cls.assemble_temporal_signals(all_signals),
            media=cls.assemble_media_signals(all_signals),
            conversation=cls.assemble_conversation_signals(all_signals),
        )
