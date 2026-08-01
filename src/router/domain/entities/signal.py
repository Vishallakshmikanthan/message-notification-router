"""SignalBundle Domain Entity encapsulating all pre-computed analytical signals."""

from dataclasses import dataclass, field
from typing import Any

from router.domain.value_objects.risk_level import RiskLevel


@dataclass(frozen=True)
class SignalBundle:
    """Immutable bundle containing all 7 signal engine module calculations."""

    message_id: str

    # 3A: User Preference & Fatigue Signals
    is_quiet_hours: bool = False
    notification_fatigue_score: float = 0.0
    user_engagement_score: float = 0.0

    # 3B: Group Context Signals
    group_relevance_score: float = 0.0
    is_admin_message: bool = False
    group_is_muted_by_user: bool = False

    # 3C: Business Reputation Signals
    business_trust_score: float = 0.0
    user_opted_in: bool = True
    business_account_age_days: int = 0

    # 3D: Risk & Fraud Signals
    forward_chain_depth: int = 0
    scam_keyword_score: float = 0.0
    spam_repetition_score: float = 0.0
    unverified_business_flag: bool = False
    risk_level: RiskLevel = RiskLevel.NONE

    # 3E: Urgency & Relevance Signals
    urgency_keywords_present: bool = False
    personal_sender_known: bool = False
    urgency_score: float = 0.0

    # 3F: History & Evidence Candidate Signals
    candidate_evidence_ids: list[str] = field(default_factory=list)

    # 3G: Fatigue & Repetition Signals
    messages_received_today_from_sender: int = 0
    repetition_flag: bool = False

    # Metadata & Quality
    completeness_score: float = 1.0
    raw_signals: dict[str, Any] = field(default_factory=dict)
