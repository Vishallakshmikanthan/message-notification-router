"""HistoryRepository implementation matching message_history.csv."""

from collections.abc import Sequence

from router.domain.entities.history import HistoricalMessage
from router.domain.ports.repository_ports import IHistoryRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class HistoryRepository(BaseRepository[HistoricalMessage, str], IHistoryRepository):
    """Stores historical chat log trajectories."""

    def __init__(self) -> None:
        """Initialize HistoryRepository trajectory indexes."""
        super().__init__()
        self._trajectory_index: dict[tuple[str, str], list[HistoricalMessage]] = {}

    def add(self, key: str, entity: HistoricalMessage) -> None:
        """Add historical message entity and update trajectory index."""
        super().add(key, entity)
        self._trajectory_index.setdefault((entity.user_id, entity.sender_id), []).append(entity)

    def get_trajectory(self, user_id: str, sender_id: str) -> Sequence[HistoricalMessage]:
        """Get pre-sorted chronological trajectory between user and sender."""
        trajectory = self._trajectory_index.get((user_id, sender_id), [])
        return sorted(trajectory, key=lambda msg: msg.created_at)

    def clear(self) -> None:
        """Clear store and trajectory indexes."""
        super().clear()
        self._trajectory_index.clear()
