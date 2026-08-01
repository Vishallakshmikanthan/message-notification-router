"""NotificationSummaryRepository implementation matching daily_notification_summary.csv."""

from router.domain.entities.history import DailyNotificationSummary
from router.domain.ports.repository_ports import INotificationSummaryRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class NotificationSummaryRepository(
    BaseRepository[DailyNotificationSummary, str], INotificationSummaryRepository
):
    """Stores daily aggregated user notification metric time-series summaries."""

    def __init__(self) -> None:
        """Initialize NotificationSummaryRepository composite index."""
        super().__init__()
        self._summary_index: dict[tuple[str, str], DailyNotificationSummary] = {}

    def add_summary(self, summary: DailyNotificationSummary) -> None:
        """Add daily notification summary entity."""
        key = f"{summary.user_id}_{summary.date_str}"
        super().add(key, summary)
        self._summary_index[(summary.user_id, summary.date_str)] = summary

    def get_summary(self, user_id: str, date_str: str) -> DailyNotificationSummary | None:
        """Get user notification summary for given date."""
        return self._summary_index.get((user_id, date_str))

    def clear(self) -> None:
        """Clear store and summary index."""
        super().clear()
        self._summary_index.clear()
