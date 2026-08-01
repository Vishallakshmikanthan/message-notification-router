"""MessageContext Domain Entity representing enriched master evaluation context as defined in message_context.md."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.signal import SignalBundle
from router.domain.entities.sub_contexts import (
    DEFAULT_BEHAVIOUR_CONTEXT,
    DEFAULT_BUSINESS_CONTEXT,
    DEFAULT_CONVERSATION_CONTEXT,
    DEFAULT_GROUP_CONTEXT,
    DEFAULT_HISTORY_CONTEXT,
    DEFAULT_MEDIA_CONTEXT,
    DEFAULT_NOTIFICATION_CONTEXT,
    DEFAULT_RELATIONSHIP_CONTEXT,
    DEFAULT_USER_CONTEXT,
    BehaviourContext,
    BusinessContext,
    ConversationContext,
    GroupContext,
    HistoryContext,
    MediaContext,
    NotificationContext,
    RelationshipContext,
    UserContext,
)
from router.domain.entities.user import User


@dataclass(frozen=True)
class ContextMetadata:
    """System assembly metadata for context tracking and auditing."""

    context_id: str
    assembled_at: str
    assembly_latency_ms: float
    completeness_score: float


@dataclass(frozen=True)
class CoreMessageContext:
    """Normalized core message content and flags."""

    message_id: str
    raw_text_content: str
    cleaned_text: str
    message_type: str  # TEXT, IMAGE, VOICE, DOCUMENT, VIDEO, LOCATION
    char_count: int
    word_count: int
    contains_links: bool
    contains_phone_numbers: bool
    is_forwarded: bool
    forward_count: int
    is_frequently_forwarded: bool


@dataclass(frozen=True)
class TemporalInformation:
    """Temporal attributes derived from message epoch timestamp."""

    timestamp_epoch_ms: int
    iso_timestamp: str
    day_of_week: str
    hour_of_day: int
    is_weekend: bool
    is_working_hours: bool


@dataclass(frozen=True)
class ContextQualityMetrics:
    """Context completeness metrics and structural validation status."""

    completeness_score: float
    sub_context_scores: Dict[str, float] = field(default_factory=dict)
    is_anonymous_sender: bool = False
    missing_fields: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MessageContext:
    """Master immutable MessageContext container as specified in message_context.md."""

    # 1. Master Metadata & Core Schema
    context_metadata: ContextMetadata = field(
        default_factory=lambda: ContextMetadata(
            context_id="NONE",
            assembled_at=datetime.now(timezone.utc).isoformat(),
            assembly_latency_ms=0.0,
            completeness_score=1.0,
        )
    )
    core_message: CoreMessageContext = field(
        default_factory=lambda: CoreMessageContext(
            message_id="NONE",
            raw_text_content="",
            cleaned_text="",
            message_type="TEXT",
            char_count=0,
            word_count=0,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    temporal_info: TemporalInformation = field(
        default_factory=lambda: TemporalInformation(
            timestamp_epoch_ms=0,
            iso_timestamp=datetime.now(timezone.utc).isoformat(),
            day_of_week="MONDAY",
            hour_of_day=0,
            is_weekend=False,
            is_working_hours=True,
        )
    )

    # 2. Key Entities (Sender & Receiver)
    sender: UserContext = field(default_factory=lambda: DEFAULT_USER_CONTEXT)
    receiver: UserContext = field(default_factory=lambda: DEFAULT_USER_CONTEXT)

    # 3. 9 Sub-Context Objects
    conversation: ConversationContext = field(default_factory=lambda: DEFAULT_CONVERSATION_CONTEXT)
    group: GroupContext = field(default_factory=lambda: DEFAULT_GROUP_CONTEXT)
    business: BusinessContext = field(default_factory=lambda: DEFAULT_BUSINESS_CONTEXT)
    media: MediaContext = field(default_factory=lambda: DEFAULT_MEDIA_CONTEXT)
    history: HistoryContext = field(default_factory=lambda: DEFAULT_HISTORY_CONTEXT)
    notification_behaviour: NotificationContext = field(
        default_factory=lambda: DEFAULT_NOTIFICATION_CONTEXT
    )
    relationship: RelationshipContext = field(default_factory=lambda: DEFAULT_RELATIONSHIP_CONTEXT)
    behaviour_stats: BehaviourContext = field(default_factory=lambda: DEFAULT_BEHAVIOUR_CONTEXT)

    # 4. Quality Metrics
    quality_metrics: ContextQualityMetrics = field(
        default_factory=lambda: ContextQualityMetrics(completeness_score=1.0)
    )

    # Backward compatibility attributes for Phase 1-3 integrations
    message_id: str = ""
    user_id: str = ""
    sender_id: str = ""
    conversation_type: Any = "personal"
    message_text: str = ""
    created_at: Optional[datetime] = None
    forwarded_count: int = 0
    user: Optional[User] = None
    is_quiet_hours: bool = False
    notification_load_today: int = 0
    group_member: Optional[GroupMember] = None
    group_muted: bool = False
    user_business_history: Optional[UserBusinessHistory] = None
    media_id: Optional[str] = None
    media_type: Optional[str] = None
    media_ocr_text: Optional[str] = None
    media_vlm_caption: Optional[str] = None
    media_category: Optional[str] = None
    voice_transcript: Optional[str] = None
    voice_duration_seconds: float = 0.0
    recent_history: List[Dict[str, Any]] = field(default_factory=list)
    user_reactions: Dict[str, int] = field(default_factory=dict)
    signals: Optional[SignalBundle] = None

    # Property aliases for Phase 1-3 sub-context references
    @property
    def user_context(self) -> UserContext:
        """Alias for receiver or sender UserContext."""
        return self.sender

    @property
    def group_context(self) -> GroupContext:
        """Alias for group GroupContext."""
        return self.group

    @property
    def business_context(self) -> BusinessContext:
        """Alias for business BusinessContext."""
        return self.business

    @property
    def media_context(self) -> MediaContext:
        """Alias for media MediaContext."""
        return self.media

    @property
    def history_context(self) -> HistoryContext:
        """Alias for history HistoryContext."""
        return self.history

    @property
    def notification_context(self) -> NotificationContext:
        """Alias for notification_behaviour NotificationContext."""
        return self.notification_behaviour

    @property
    def relationship_context(self) -> RelationshipContext:
        """Alias for relationship RelationshipContext."""
        return self.relationship

    @property
    def conversation_context(self) -> ConversationContext:
        """Alias for conversation ConversationContext."""
        return self.conversation

    @property
    def behaviour_context(self) -> BehaviourContext:
        """Alias for behaviour_stats BehaviourContext."""
        return self.behaviour_stats
