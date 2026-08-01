"""User Domain Entity representing recipient user profile."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class User:
    """Recipient user profile entity matching users.csv schema."""

    user_id: str
    user_name: str
    do_not_disturb_window: str | None = None
    open_count_30d: int = 0
    reply_count_30d: int = 0
    dismiss_count_30d: int = 0
    spam_report_count: int = 0
    created_at: datetime = field(default_factory=_utc_now)

    @property
    def total_interactions_30d(self) -> int:
        """Calculate total recorded user interactions over 30 days."""
        return self.open_count_30d + self.reply_count_30d + self.dismiss_count_30d

    @property
    def open_rate(self) -> float:
        """Calculate historical open rate baseline."""
        total = self.total_interactions_30d
        return self.open_count_30d / total if total > 0 else 0.0

    @property
    def reply_rate(self) -> float:
        """Calculate historical reply rate baseline."""
        total = self.total_interactions_30d
        return self.reply_count_30d / total if total > 0 else 0.0
