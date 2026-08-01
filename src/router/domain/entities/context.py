"""MessageContext Domain Entity representing enriched multi-source evaluation context."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.message import Message
from router.domain.entities.signal import SignalBundle
from router.domain.entities.sub_contexts import (
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
class MessageContext:
    """Unified enriched context object synthesized for downstream signal and routing engines."""

    # Core message
    message_id: str
    user_id: str
    sender_id: str
    conversation_type: Literal["personal", "group", "business"]
    message_text: str
    created_at: datetime
    forwarded_count: int = 0

    # User profile & preferences
    user: User | None = None
    is_quiet_hours: bool = False
    notification_load_today: int = 0

    # Group sub-context
    group: Group | None = None
    group_member: GroupMember | None = None
    group_muted: bool = False

    # Business sub-context
    business: BusinessAccount | None = None
    user_business_history: UserBusinessHistory | None = None

    # Media sub-context enrichment
    media_id: str | None = None
    media_type: Literal["image", "voice"] | None = None
    media_ocr_text: str | None = None
    media_vlm_caption: str | None = None
    media_category: str | None = None
    voice_transcript: str | None = None
    voice_duration_seconds: float = 0.0

    # Trajectory & reaction history
    recent_history: list[dict[str, Any]] = field(default_factory=list)
    user_reactions: dict[str, int] = field(default_factory=dict)

    # 9 Structured Sub-Context Objects
    user_context: Optional[UserContext] = None
    group_context: Optional[GroupContext] = None
    business_context: Optional[BusinessContext] = None
    media_context: Optional[MediaContext] = None
    history_context: Optional[HistoryContext] = None
    notification_context: Optional[NotificationContext] = None
    relationship_context: Optional[RelationshipContext] = None
    conversation_context: Optional[ConversationContext] = None
    behaviour_context: Optional[BehaviourContext] = None

    # Optional computed signals bundle
    signals: SignalBundle | None = None
