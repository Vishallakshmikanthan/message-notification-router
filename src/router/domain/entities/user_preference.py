"""User Preference Domain Entity."""

from dataclasses import dataclass, field
from datetime import time


@dataclass(frozen=True)
class UserPreference:
    """Enterprise domain entity representing user notification preferences."""

    user_id: str
    vip_contacts: set[str] = field(default_factory=set)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None

    def is_vip_sender(self, phone_number: str) -> bool:
        """Evaluate whether a sender phone number is marked as VIP."""
        return phone_number in self.vip_contacts
