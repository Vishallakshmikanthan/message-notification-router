"""Notification Action Value Object representing routing decisions."""

from enum import StrEnum


class NotificationAction(StrEnum):
    """Supported routing notification actions."""

    NOTIFY = "notify"
    DIGEST = "digest"
    MUTE = "mute"
