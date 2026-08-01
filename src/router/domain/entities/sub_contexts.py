"""Explicit Data Models for 9 Sub-Context Objects as specified in context_models.md."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class UserContext:
    """Encapsulates identity, settings, and metadata for a user (users.csv)."""

    user_id: str
    display_name: str
    phone_number: str
    user_type: str  # INDIVIDUAL, BUSINESS, SYSTEM_BOT
    registration_timestamp: int
    account_age_days: int
    preferred_language: str
    timezone: str
    is_verified: bool
    is_registered_user: bool = True


@dataclass(frozen=True)
class GroupContext:
    """Encapsulates workspace, group type, participant structure, and sender role."""

    group_id: str
    group_name: str
    group_type: str  # FAMILY, WORK, COMMUNITY, COMMERCIAL, DIRECT_CHAT
    created_at_timestamp: int
    total_member_count: int
    is_announcement_only: bool
    sender_role: str  # ADMIN, MEMBER, NON_MEMBER
    sender_joined_at: int
    sender_is_muted_in_group: bool


@dataclass(frozen=True)
class BusinessContext:
    """Encapsulates commercial account verification, vertical, response SLA, and catalog status."""

    business_id: str
    business_name: str
    category: str  # RETAIL, BANKING, SERVICES, HEALTHCARE, NON_BUSINESS
    verification_status: str  # VERIFIED_OFFICIAL, STANDARD, UNVERIFIED
    support_email: str
    catalog_enabled: bool
    expected_sla_minutes: int
    is_business_account: bool = True


from router.domain.entities.media_context import ImageContext, VoiceContext


@dataclass(frozen=True)
class MediaContext:
    """Unifies visual OCR, acoustic voice analysis, and multimodal metadata."""

    media_id: str
    media_type: str  # TEXT_ONLY, IMAGE, VOICE, DOCUMENT, MULTIMODAL_COMBO
    sha256_hash: str
    has_media: bool = True
    image_context: Optional[ImageContext] = None
    voice_context: Optional[VoiceContext] = None
    validation_status: str = "VALIDATED"  # VALIDATED, PARTIAL, CORRUPTED, FAILED
    processing_latency_ms: float = 0.0
    error_flags: List[str] = field(default_factory=list)
    created_at: str = ""
    # Backward compatibility attributes
    image_summary: str = ""
    image_category: str = ""
    ocr_extracted_text: str = ""
    image_risk_score: float = 0.0
    voice_transcript: str = ""
    voice_duration_seconds: float = 0.0
    acoustic_tone: str = "NEUTRAL"  # CALM, URGENT, SHOUTING, NEUTRAL
    voice_urgency_score: float = 0.0



@dataclass(frozen=True)
class HistoryContext:
    """Encapsulates recent message events, historical conversation logs, and past interactions."""

    historical_message_count: int
    last_interaction_timestamp: int
    days_since_last_interaction: float
    recent_event_types: List[str] = field(default_factory=list)
    historical_similar_message_count: int = 0


@dataclass(frozen=True)
class NotificationContext:
    """Encapsulates historical delivery, open, and response behaviors for notification traffic."""

    user_daily_notification_volume: int
    historical_open_rate: float
    historical_avg_response_seconds: float
    daily_notification_cap: int = 50


@dataclass(frozen=True)
class RelationshipContext:
    """Models relational ties, commercial engagement histories, and group authority dynamics."""

    relationship_type: str  # PEER_TO_PEER, CUSTOMER_BUSINESS, GROUP_MEMBER, UNKNOWN
    customer_total_orders: int = 0
    customer_total_spend: float = 0.0
    commercial_tier: str = "NON_CUSTOMER"  # VIP, REGULAR, NEW, NON_CUSTOMER
    is_contacts_saved: bool = False


@dataclass(frozen=True)
class ConversationContext:
    """Encapsulates current thread state, message burst counts, and active participant metrics."""

    conversation_id: str
    is_group_chat: bool
    active_participant_count: int = 1
    burst_message_count: int = 1
    thread_cadence: str = "EPISODIC"  # FAST_REALTIME, EPISODIC, DORMANT


@dataclass(frozen=True)
class BehaviourContext:
    """Encapsulates aggregate statistical patterns of user activity and message generation habits."""

    sender_avg_daily_messages: float = 0.0
    sender_forward_ratio: float = 0.0
    receiver_quiet_hours_active: bool = False
