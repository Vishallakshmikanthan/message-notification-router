"""Message ID Value Object encapsulating message identifier invariant validation."""

from dataclasses import dataclass

from router.core.exceptions.base_exceptions import RouterError


class InvalidMessageIdError(RouterError):
    """Exception raised when a MessageId string format is invalid."""

    pass


@dataclass(frozen=True)
class MessageId:
    """Immutable Message Identifier Value Object."""

    value: str

    def __post_init__(self) -> None:
        """Validate non-empty string constraint."""
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise InvalidMessageIdError("MessageId must be a non-empty string.")

    def __str__(self) -> str:
        """Return raw string representation."""
        return self.value
