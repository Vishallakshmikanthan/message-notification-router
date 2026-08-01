"""Message Domain Entity."""

from dataclasses import dataclass
from datetime import datetime
from router.domain.value_objects.message_id import MessageId


@dataclass(frozen=True)
class Message:
    """Core enterprise immutable Message entity."""

    message_id: MessageId
    sender_phone: str
    payload_text: str | None
    timestamp: datetime

    def has_text(self) -> bool:
        """Check if message contains textual payload."""
        return self.payload_text is not None and len(self.payload_text.strip()) > 0
