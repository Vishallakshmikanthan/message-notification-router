"""ContextRepositoryRegistry providing unified dependency injection for context assembly data sources."""


from router.domain.ports.media_ports import MediaCachePort
from router.domain.ports.repository_ports import (
    IBusinessRepository,
    IEventRepository,
    IGroupRepository,
    IHistoryRepository,
    IMessageRepository,
    INotificationSummaryRepository,
    IUserRepository,
)


class ContextRepositoryRegistry:
    """Unified repository registry providing dependency injection for context assembly."""

    def __init__(
        self,
        messages_repo: IMessageRepository | None = None,
        users_repo: IUserRepository | None = None,
        groups_repo: IGroupRepository | None = None,
        business_accounts_repo: IBusinessRepository | None = None,
        message_history_repo: IHistoryRepository | None = None,
        message_events_repo: IEventRepository | None = None,
        daily_notification_summary_repo: INotificationSummaryRepository | None = None,
        multimodal_cache: MediaCachePort | None = None,
    ) -> None:
        """Initialize ContextRepositoryRegistry with optional repository instances."""
        self.messages_repo = messages_repo
        self.users_repo = users_repo
        self.groups_repo = groups_repo
        self.business_accounts_repo = business_accounts_repo
        self.message_history_repo = message_history_repo
        self.message_events_repo = message_events_repo
        self.daily_notification_summary_repo = daily_notification_summary_repo
        self.multimodal_cache = multimodal_cache
