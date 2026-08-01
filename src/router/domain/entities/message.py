"""Primary Message, HistoricalMessage, MessageEvent, and DailyNotificationSummary Entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from router.domain.value_objects.notification_action import NotificationAction


@dataclass(frozen=True)
class Message:
    """Incoming primary evaluation message entity matching messages.csv schema."""

    message_id: str
    user_id: str
    conversation_type: Literal["personal", "group", "business"]
    sender_id: str
    message_text: str
    created_at: datetime
    group_id: str | None = None
    business_id: str | None = None
    media_id: str | None = None
    media_type: Literal["image", "voice"] | None = None
    forwarded_count: int = 0


@dataclass(frozen=True)
class HistoricalMessage:
    """Historical chat log message entity matching message_history.csv."""

    message_id: str
    user_id: str
    sender_id: str
    message_text: str
    created_at: datetime
    group_id: str | None = None
    business_id: str | None = None
    forwarded_count: int = 0


@dataclass(frozen=True)
class MessageEvent:
    """Message user reaction/event log matching message_events.csv."""

    event_id: str
    user_id: str
    message_id: str
    event_type: Literal["delivered", "read", "replied", "dismissed", "muted"]
    timestamp: datetime


@dataclass(frozen=True)
class DailyNotificationSummary:
    """Daily notification metric time-series summary matching daily_notification_summary.csv."""

    user_id: str
    date_str: str  # YYYY-MM-DD
    total_notifications_received: int = 0
    total_opened: int = 0
    total_dismissed: int = 0
    total_muted: int = 0
