"""Primary Message Entity matching messages.csv schema."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Message:
    """Incoming primary evaluation message entity matching messages.csv schema."""

    message_id: str
    user_id: str
    conversation_type: str  # personal, group, business
    message_text: str = ""
    sender_id: Optional[str] = None
    sender_user_id: Optional[str] = None
    group_id: Optional[str] = None
    business_id: Optional[str] = None
    media_id: Optional[str] = None
    media_type: Optional[str] = None
    forwarded_count: int = 0
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.sender_id and self.sender_user_id:
            object.__setattr__(self, "sender_id", self.sender_user_id)
        elif not self.sender_user_id and self.sender_id:
            object.__setattr__(self, "sender_user_id", self.sender_id)
