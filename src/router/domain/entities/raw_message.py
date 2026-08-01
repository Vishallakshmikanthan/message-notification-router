"""RawMessagePayload entity for Stage 0 context assembly ingestion."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RawMessagePayload:
    """Inbound raw message event payload from gateway/webhook."""

    message_id: str
    sender_phone: str
    receiver_phone: str
    group_id: str = "NONE"
    business_id: str = "NONE"
    content: str = ""
    timestamp: int = 0
    media_hash: str = ""
    media_type: str = "TEXT"
    is_forwarded: bool = False
    forward_count: int = 0
