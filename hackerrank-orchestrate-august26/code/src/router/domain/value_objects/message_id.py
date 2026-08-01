"""Message ID Value Object."""

from dataclasses import dataclass
from router.domain.exceptions.domain_exceptions import InvalidMessageIdError


@dataclass(frozen=True)
class MessageId:
    """Immutable Message Identifier Value Object."""

    value: str

    def __post_init__(self) -> None:
        """Validate raw message identifier."""
        if not self.value or not isinstance(self.value, str):
            raise InvalidMessageIdError("Message ID must be a non-empty string.")

    @classmethod
    def from_raw(cls, raw_id: str) -> "MessageId":
        """Factory method creating MessageId from raw string."""
        return cls(value=raw_id)
