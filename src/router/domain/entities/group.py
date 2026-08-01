"""Group and GroupMember Domain Entities representing WhatsApp groups."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Group:
    """WhatsApp group profile entity matching groups.csv schema."""

    group_id: str
    group_name: str
    group_type: str
    member_count: int
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class GroupMember:
    """Group membership junction entity matching group_members.csv schema."""

    group_id: str
    user_id: str
    role: str  # e.g., 'admin', 'member'
    is_muted: bool = False
    activity_score: float = 0.0
    joined_at: datetime = field(default_factory=_utc_now)

    @property
    def is_admin(self) -> bool:
        """Check if user holds administrator privileges in group."""
        return self.role.lower() == "admin"
