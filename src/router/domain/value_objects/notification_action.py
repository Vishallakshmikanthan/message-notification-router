"""Notification Action Value Object."""

from enum import StrEnum, auto


class NotificationAction(StrEnum):
    """Enumeration of valid routing actions for processed messages."""

    NOTIFY = auto()
    DIGEST = auto()
    MUTE = auto()
