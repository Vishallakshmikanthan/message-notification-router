"""ContextRepositoryRegistry providing unified dependency injection for context assembly data sources."""

from typing import Optional

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
        messages_repo: Optional[IMessageRepository] = None,
        users_repo: Optional[IUserRepository] = None,
        groups_repo: Optional[IGroupRepository] = None,
        business_accounts_repo: Optional[IBusinessRepository] = None,
        message_history_repo: Optional[IHistoryRepository] = None,
        message_events_repo: Optional[IEventRepository] = None,
        daily_notification_summary_repo: Optional[INotificationSummaryRepository] = None,
        multimodal_cache: Optional[MediaCachePort] = None,
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
