"""EventRepository implementation matching message_events.csv."""

from collections.abc import Sequence

from router.domain.entities.history import MessageEvent
from router.domain.ports.repository_ports import IEventRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class EventRepository(BaseRepository[MessageEvent, str], IEventRepository):
    """Stores message delivery, read, reply, and dismiss reaction event logs."""

    def __init__(self) -> None:
        """Initialize EventRepository user reaction index."""
        super().__init__()
        self._user_events_index: dict[str, list[MessageEvent]] = {}

    def add(self, key: str, entity: MessageEvent) -> None:
        """Add message event entity and update user index."""
        super().add(key, entity)
        self._user_events_index.setdefault(entity.user_id, []).append(entity)

    def get_user_events(self, user_id: str) -> Sequence[MessageEvent]:
        """Get all message events associated with user."""
        return self._user_events_index.get(user_id, [])

    def clear(self) -> None:
        """Clear store and user event index."""
        super().clear()
        self._user_events_index.clear()
