"""Message Type Value Object representing domain taxonomy of messages."""

from enum import StrEnum


class MessageType(StrEnum):
    """Domain classification categories for WhatsApp messages."""

    PERSONAL = "personal"
    URGENT = "urgent"
    EVENT = "event"
    PAYMENT = "payment"
    BUSINESS_UPDATE = "business_update"
    PROMOTION = "promotion"
    GREETING = "greeting"
    FORWARD = "forward"
    SPAM = "spam"
    SCAM = "scam"
    UNKNOWN = "unknown"
