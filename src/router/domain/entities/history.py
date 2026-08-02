"""History, Event, and Notification Summary Domain Entities."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class HistoricalMessage:
    """Historical message trajectory log entity mapping message_history.csv."""

    message_id: str
    user_id: str
    sender_id: str
    conversation_type: str
    message_text: str
    created_at: datetime
    business_id: str | None = None
    group_id: str | None = None


@dataclass(frozen=True)
class MessageEvent:
    """Message status delivery and reaction event entity mapping message_events.csv."""

    event_id: str
    message_id: str
    user_id: str
    event_type: str
    event_timestamp: datetime
    details: str | None = None


@dataclass(frozen=True)
class DailyNotificationSummary:
    """Daily notification metric time-series entity mapping daily_notification_summary.csv."""

    summary_id: str
    user_id: str
    summary_date: date
    messages_received: int = 0
    notifications_opened: int = 0
    notifications_dismissed: int = 0
    avg_response_time_seconds: float = 0.0

    @property
    def date_str(self) -> str:
        """Return ISO formatted date string representation (YYYY-MM-DD)."""
        return self.summary_date.isoformat()
