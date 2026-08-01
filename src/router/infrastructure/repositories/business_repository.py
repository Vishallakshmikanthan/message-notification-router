"""BusinessRepository implementation matching business_accounts.csv and user_business_history.csv."""

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.ports.repository_ports import IBusinessRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class BusinessRepository(BaseRepository[BusinessAccount, str], IBusinessRepository):
    """Stores business profiles and user-business interaction histories."""

    def __init__(self) -> None:
        """Initialize BusinessRepository history composite index."""
        super().__init__()
        self._history_index: dict[tuple[str, str], UserBusinessHistory] = {}

    def add_user_history(self, history: UserBusinessHistory) -> None:
        """Add user-business history entity."""
        self._history_index[(history.user_id, history.business_id)] = history

    def get_user_history(self, user_id: str, business_id: str) -> UserBusinessHistory | None:
        """Get user business interaction history entity by composite key."""
        return self._history_index.get((user_id, business_id))

    def clear(self) -> None:
        """Clear store and history indexes."""
        super().clear()
        self._history_index.clear()
