"""SignalBundle Domain Entity encapsulating all computed analytical signals as specified in signal_bundle.md."""

from dataclasses import dataclass, field
from typing import Any

from router.domain.value_objects.risk_level import RiskLevel


@dataclass(frozen=True)
class SignalExplainability:
    """Standardized explainability envelope for an individual signal computation."""

    raw_value: float
    primary_driver: str
    rationale: str
    contributing_factors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalValue:
    """Standardized atomic signal value container guaranteeing score bounding and confidence estimation."""

    score: float  # Bounded in range [0.0, 1.0]
    confidence: float  # Bounded in range [0.0, 1.0]
    explainability: SignalExplainability


@dataclass(frozen=True)
class SignalBundleMetadata:
    """Metadata envelope for SignalBundle computation execution."""

    bundle_id: str
    message_id: str
    computed_at: str
    calculation_latency_ms: float
    global_confidence: float
    global_completeness: float


@dataclass(frozen=True)
class BehaviourSignals:
    """User interaction and notification intake dynamics signals."""

    notification_fatigue: SignalValue
    reading_responsiveness: SignalValue
    reply_velocity: SignalValue
    dismiss_propensity: SignalValue
    ignore_propensity: SignalValue
    time_of_day_affinity: SignalValue
    weekend_responsiveness: SignalValue
    group_engagement: SignalValue
    business_engagement: SignalValue


@dataclass(frozen=True)
class RiskSignals:
    """Safety hazard, scam, fraud, and spam risk signals."""

    spam: SignalValue
    scam: SignalValue
    fraud_indicator: SignalValue
    business_trust: SignalValue  # Inverted risk rating representing business authenticity/risk
    forward_chain_risk: SignalValue
    unknown_sender_risk: SignalValue
    visual_scam_risk: SignalValue
    voice_scam_risk: SignalValue


@dataclass(frozen=True)
class TrustSignals:
    """Social closeness, account authenticity, and historical reliability signals."""

    business_trust_score: SignalValue
    relationship_score: SignalValue
    known_contact_score: SignalValue
    group_reliability: SignalValue
    historical_trust: SignalValue
    interaction_strength: SignalValue


@dataclass(frozen=True)
class UrgencySignals:
    """Time criticality, emergency, payment, and meeting signals."""

    emergency: SignalValue
    time_sensitive_event: SignalValue
    payment: SignalValue
    deadline: SignalValue
    meeting: SignalValue
    appointment: SignalValue
    family_emergency: SignalValue
    health_emergency: SignalValue
    critical_announcement: SignalValue


@dataclass(frozen=True)
class RelationshipSignals:
    """Granular social graph metrics between sender and receiver."""

    tie_strength: SignalValue
    intimacy_score: SignalValue
    reciprocity_ratio: SignalValue


@dataclass(frozen=True)
class BusinessSignals:
    """Commercial, transactional, and promotional intent signals."""

    commercial_intent: SignalValue
    transactional_intent: SignalValue
    promotional_intent: SignalValue


@dataclass(frozen=True)
class GroupSignals:
    """Group workspace importance and targeting signals."""

    group_importance: SignalValue
    direct_mention: SignalValue


@dataclass(frozen=True)
class HistorySignals:
    """Long-term historical engagement metrics."""

    historical_open_rate: SignalValue
    historical_reply_rate: SignalValue


@dataclass(frozen=True)
class TemporalSignals:
    """Local time and quiet hours alignment signals."""

    quiet_hours_active: SignalValue


@dataclass(frozen=True)
class MediaSignals:
    """Multimodal payload information density signals."""

    media_importance: SignalValue


@dataclass(frozen=True)
class ConversationSignals:
    """Active conversation thread momentum signals."""

    conversation_importance: SignalValue


@dataclass(frozen=True)
class SignalBundle:
    """Master immutable SignalBundle container as specified in signal_bundle.md."""

    metadata: SignalBundleMetadata
    behaviour: BehaviourSignals
    risk: RiskSignals
    trust: TrustSignals
    urgency: UrgencySignals
    relationship: RelationshipSignals
    business: BusinessSignals
    group: GroupSignals
    history: HistorySignals
    temporal: TemporalSignals
    media: MediaSignals
    conversation: ConversationSignals

    # Backward compatibility property accessors for Phase 1-4 components
    @property
    def message_id(self) -> str:
        """Alias for metadata.message_id."""
        return self.metadata.message_id

    @property
    def is_quiet_hours(self) -> bool:
        """Alias for temporal.quiet_hours_active score check."""
        return self.temporal.quiet_hours_active.score >= 0.5

    @property
    def notification_fatigue_score(self) -> float:
        """Alias for behaviour.notification_fatigue.score."""
        return self.behaviour.notification_fatigue.score

    @property
    def user_engagement_score(self) -> float:
        """Alias for behaviour.reading_responsiveness.score."""
        return self.behaviour.reading_responsiveness.score

    @property
    def group_relevance_score(self) -> float:
        """Alias for group.group_importance.score."""
        return self.group.group_importance.score

    @property
    def is_admin_message(self) -> bool:
        """Alias for group.direct_mention contributing factor 'is_admin'."""
        return self.group.direct_mention.explainability.contributing_factors.get("is_admin", 0.0) >= 0.5

    @property
    def group_is_muted_by_user(self) -> bool:
        """Alias for group.group_importance contributing factor 'is_muted'."""
        return self.group.group_importance.explainability.contributing_factors.get("is_muted", 0.0) >= 0.5

    @property
    def business_trust_score(self) -> float:
        """Alias for trust.business_trust_score.score."""
        return self.trust.business_trust_score.score

    @property
    def user_opted_in(self) -> bool:
        """Alias for business.promotional_intent user opt-in flag."""
        return self.business.promotional_intent.explainability.contributing_factors.get("user_opted_in", 1.0) >= 0.5

    @property
    def forward_chain_depth(self) -> int:
        """Alias for risk.forward_chain_risk contributing factor 'forward_count'."""
        return int(self.risk.forward_chain_risk.explainability.contributing_factors.get("forward_count", 0))

    @property
    def scam_keyword_score(self) -> float:
        """Alias for risk.scam.score."""
        return self.risk.scam.score

    @property
    def spam_repetition_score(self) -> float:
        """Alias for risk.spam.score."""
        return self.risk.spam.score

    @property
    def unverified_business_flag(self) -> bool:
        """Alias for risk.business_trust contributing factor 'unverified'."""
        return self.risk.business_trust.explainability.contributing_factors.get("unverified", 0.0) >= 0.5

    @property
    def risk_level(self) -> RiskLevel:
        """Derives categorical RiskLevel from max risk score."""
        max_risk = max(
            self.risk.scam.score,
            self.risk.spam.score,
            self.risk.fraud_indicator.score,
            self.risk.visual_scam_risk.score,
            self.risk.voice_scam_risk.score,
        )
        if max_risk >= 0.8:
            return RiskLevel.CRITICAL
        elif max_risk >= 0.5 or self.forward_chain_depth > 5:
            return RiskLevel.HIGH
        elif max_risk > 0.0:
            return RiskLevel.MEDIUM
        return RiskLevel.NONE

    @property
    def urgency_keywords_present(self) -> bool:
        """Alias for emergency or urgency keywords detected."""
        return (
            self.urgency.emergency.score > 0.0
            or self.urgency.time_sensitive_event.score > 0.0
            or self.urgency.payment.score > 0.0
            or self.urgency.deadline.score > 0.0
            or self.urgency.meeting.score > 0.0
        )

    @property
    def personal_sender_known(self) -> bool:
        """Alias for trust.known_contact_score.score > 0.0."""
        return self.trust.known_contact_score.score > 0.0

    @property
    def urgency_score(self) -> float:
        """Max urgency score across all urgency dimensions."""
        return max(
            self.urgency.emergency.score,
            self.urgency.time_sensitive_event.score,
            self.urgency.payment.score,
            self.urgency.deadline.score,
            self.urgency.meeting.score,
            self.urgency.appointment.score,
            self.urgency.family_emergency.score,
            self.urgency.health_emergency.score,
            self.urgency.critical_announcement.score,
        )

    @property
    def candidate_evidence_ids(self) -> list[str]:
        """Returns list of evidence driver IDs across computed active signals."""
        evidence: list[str] = []
        for category in [
            self.urgency,
            self.risk,
            self.trust,
            self.behaviour,
            self.relationship,
            self.business,
            self.group,
            self.history,
            self.temporal,
            self.media,
            self.conversation,
        ]:
            for attr_name in dir(category):
                if not attr_name.startswith("_"):
                    val = getattr(category, attr_name)
                    if isinstance(val, SignalValue) and val.explainability.primary_driver != "NONE":
                        evidence.append(val.explainability.primary_driver)
        return list(dict.fromkeys(evidence))

    @property
    def completeness_score(self) -> float:
        """Alias for metadata.global_completeness."""
        return self.metadata.global_completeness

    @property
    def raw_signals(self) -> dict[str, Any]:
        """Returns dict mapping signal names to score values for legacy consumers."""
        result: dict[str, Any] = {}
        for cat_name in ["behaviour", "risk", "trust", "urgency", "relationship", "business", "group", "history", "temporal", "media", "conversation"]:
            cat_obj = getattr(self, cat_name)
            for attr in dir(cat_obj):
                if not attr.startswith("_"):
                    val = getattr(cat_obj, attr)
                    if isinstance(val, SignalValue):
                        result[f"{cat_name}.{attr}"] = val.score
        return result
