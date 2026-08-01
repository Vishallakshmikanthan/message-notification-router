"""User Preference domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UserPreference:
    """Domain model representing explicit and implicit user routing preferences."""

    user_id: str
    quiet_hours_start: str | None = None  # e.g., "22:00"
    quiet_hours_end: str | None = None    # e.g., "07:00"
    vip_senders: list[str] = field(default_factory=list)
    muted_senders: list[str] = field(default_factory=list)
    muted_groups: list[str] = field(default_factory=list)
    allow_promotions: bool = True
    updated_at: datetime = field(default_factory=_utc_now)
