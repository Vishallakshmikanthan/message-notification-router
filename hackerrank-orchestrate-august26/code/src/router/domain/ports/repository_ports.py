"""Abstract repository port definitions for enterprise domain objects."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from router.domain.entities.message import Message
    from router.domain.entities.user_preference import UserPreference
    from router.domain.value_objects.message_id import MessageId


class MessageRepositoryPort(ABC):
    """Abstract Port for persisting and retrieving Message domain entities."""

    @abstractmethod
    async def save(self, message: "Message") -> None:
        """Persist a message entity."""
        pass

    @abstractmethod
    async def get_by_id(self, message_id: "MessageId") -> Optional["Message"]:
        """Retrieve a message by its domain identifier."""
        pass


class UserPreferenceRepositoryPort(ABC):
    """Abstract Port for user preference persistence."""

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional["UserPreference"]:
        """Fetch user preferences by user unique identifier."""
        pass

    @abstractmethod
    async def save(self, preference: "UserPreference") -> None:
        """Persist user preference settings."""
        pass
