"""MessageRepository implementation matching messages.csv dataset."""

from collections.abc import Sequence

from router.domain.entities.message import Message
from router.domain.ports.repository_ports import IMessageRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class MessageRepository(BaseRepository[Message, str], IMessageRepository):
    """Stores and indexes primary incoming evaluation messages."""

    def __init__(self) -> None:
        """Initialize MessageRepository secondary indexes."""
        super().__init__()
        self._user_index: dict[str, list[Message]] = {}

    def add(self, key: str, entity: Message) -> None:
        """Add message to primary and secondary user index."""
        super().add(key, entity)
        self._user_index.setdefault(entity.user_id, []).append(entity)

    def get_by_user_id(self, user_id: str) -> Sequence[Message]:
        """Get messages by recipient user ID."""
        return self._user_index.get(user_id, [])

    def clear(self) -> None:
        """Clear store and secondary indexes."""
        super().clear()
        self._user_index.clear()
