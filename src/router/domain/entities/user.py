"""User Domain Entity representing recipient user profile."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class User:
    """Recipient user profile entity matching users.csv schema."""

    user_id: str
    name: str = ""
    user_name: str = ""
    phone_number: str = ""
    user_type: str = "INDIVIDUAL"
    registration_date: datetime = field(default_factory=_utc_now)
    preferred_language: str = "en"
    timezone: str = "UTC"
    is_verified: bool = False
    do_not_disturb_window: Optional[str] = None
    messages_opened_30d: int = 0
    messages_replied_30d: int = 0
    notifications_dismissed_30d: int = 0
    messages_reported_30d: int = 0
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.name and self.user_name:
            object.__setattr__(self, "name", self.user_name)
        elif not self.user_name and self.name:
            object.__setattr__(self, "user_name", self.name)

    @property
    def open_count_30d(self) -> int:
        """Alias for messages_opened_30d."""
        return self.messages_opened_30d

    @property
    def reply_count_30d(self) -> int:
        """Alias for messages_replied_30d."""
        return self.messages_replied_30d

    @property
    def dismiss_count_30d(self) -> int:
        """Alias for notifications_dismissed_30d."""
        return self.notifications_dismissed_30d

    @property
    def total_interactions_30d(self) -> int:
        """Calculate total recorded user interactions over 30 days."""
        return self.messages_opened_30d + self.messages_replied_30d + self.notifications_dismissed_30d

    @property
    def open_rate(self) -> float:
        """Calculate historical open rate baseline."""
        total = self.total_interactions_30d
        return self.messages_opened_30d / total if total > 0 else 0.0

    @property
    def reply_rate(self) -> float:
        """Calculate historical reply rate baseline."""
        total = self.total_interactions_30d
        return self.messages_replied_30d / total if total > 0 else 0.0
