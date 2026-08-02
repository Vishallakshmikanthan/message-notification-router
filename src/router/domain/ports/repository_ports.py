"""Abstract Repository Interface Contracts for Domain Layer."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.history import (
    DailyNotificationSummary,
    HistoricalMessage,
    MessageEvent,
)
from router.domain.entities.media import ImageManifest, VoiceNoteManifest
from router.domain.entities.message import Message
from router.domain.entities.user import User

TEntity = TypeVar("TEntity")
TKey = TypeVar("TKey")


class IRepository(ABC, Generic[TEntity, TKey]):
    """Generic Base Repository Interface Specification."""

    @abstractmethod
    def get_by_id(self, key: TKey) -> TEntity | None:
        """Perform O(1) primary key lookup."""
        ...

    @abstractmethod
    def get_all(self) -> Sequence[TEntity]:
        """Return read-only collection of all entities."""
        ...

    @abstractmethod
    def exists(self, key: TKey) -> bool:
        """Check key presence in O(1) time."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return total number of managed records."""
        ...


class IMessageRepository(IRepository[Message, str]):
    """Message Repository Contract."""

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> Sequence[Message]:
        """Get messages by recipient user ID."""
        ...


class IUserRepository(IRepository[User, str]):
    """User Repository Contract."""

    pass


class IGroupRepository(IRepository[Group, str]):
    """Group Repository Contract."""

    @abstractmethod
    def get_member(self, group_id: str, user_id: str) -> GroupMember | None:
        """Get group member junction record."""
        ...

    @abstractmethod
    def is_admin(self, group_id: str, user_id: str) -> bool:
        """Verify admin role."""
        ...


class IBusinessRepository(IRepository[BusinessAccount, str]):
    """Business Repository Contract."""

    @abstractmethod
    def get_user_history(self, user_id: str, business_id: str) -> UserBusinessHistory | None:
        """Get user business interaction history."""
        ...


class IMediaRepository(IRepository[ImageManifest | VoiceNoteManifest, str]):
    """Media Repository Contract."""

    @abstractmethod
    def get_image(self, media_id: str) -> ImageManifest | None:
        """Get image manifest entity."""
        ...

    @abstractmethod
    def get_voice(self, media_id: str) -> VoiceNoteManifest | None:
        """Get voice note manifest entity."""
        ...


class IHistoryRepository(IRepository[HistoricalMessage, str]):
    """History Repository Contract."""

    @abstractmethod
    def get_trajectory(self, user_id: str, sender_id: str) -> Sequence[HistoricalMessage]:
        """Get pre-sorted chronological message trajectory."""
        ...


class IEventRepository(IRepository[MessageEvent, str]):
    """Event Repository Contract."""

    @abstractmethod
    def get_user_events(self, user_id: str) -> Sequence[MessageEvent]:
        """Get message events for a user."""
        ...


class INotificationSummaryRepository(IRepository[DailyNotificationSummary, str]):
    """Notification Summary Repository Contract."""

    @abstractmethod
    def get_summary(self, user_id: str, date_str: str) -> DailyNotificationSummary | None:
        """Get daily notification summary for user and date."""
        ...
