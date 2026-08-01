"""DataManager implementation implementing IDataManager interface contract and system facade."""

from typing import Any, Dict, Mapping, Optional

from router.core.logging.logger import get_logger
from router.domain.ports.cache_ports import ICacheManager
from router.domain.ports.service_ports import IDataLoader, IDataManager
from router.infrastructure.cache.cache_manager import CacheManager
from router.infrastructure.repositories.business_repository import BusinessRepository
from router.infrastructure.repositories.event_repository import EventRepository
from router.infrastructure.repositories.group_repository import GroupRepository
from router.infrastructure.repositories.history_repository import HistoryRepository
from router.infrastructure.repositories.media_repository import MediaRepository
from router.infrastructure.repositories.message_repository import MessageRepository
from router.infrastructure.repositories.notification_summary_repository import (
    NotificationSummaryRepository,
)
from router.infrastructure.repositories.user_repository import UserRepository
from router.infrastructure.storage.data_loader import DataLoader
from router.infrastructure.storage.file_manager import FileManager
from router.infrastructure.storage.quarantine_engine import QuarantineEngine
from router.infrastructure.storage.schema_validator import SchemaValidator
from router.application.data.lookup_services import (
    ChannelLookupService,
    HistoryLookupService,
    UserLookupService,
)

logger = get_logger(__name__)


class DataManager(IDataManager):
    """Central Data Layer facade and sub-system lifecycle manager."""

    def __init__(
        self,
        dataset_dir: str = "./hackerrank-orchestrate-august26/dataset",
        cache_manager: Optional[ICacheManager] = None,
    ) -> None:
        """Initialize DataManager dependencies and concrete repositories."""
        self.dataset_dir = dataset_dir

        self.user_repo = UserRepository()
        self.group_repo = GroupRepository()
        self.business_repo = BusinessRepository()
        self.media_repo = MediaRepository()
        self.history_repo = HistoryRepository()
        self.event_repo = EventRepository()
        self.summary_repo = NotificationSummaryRepository()
        self.message_repo = MessageRepository()

        self.quarantine_engine = QuarantineEngine()
        self.schema_validator = SchemaValidator(self.quarantine_engine)

        self.data_loader: IDataLoader = DataLoader(
            user_repo=self.user_repo,
            group_repo=self.group_repo,
            business_repo=self.business_repo,
            media_repo=self.media_repo,
            history_repo=self.history_repo,
            event_repo=self.event_repo,
            summary_repo=self.summary_repo,
            message_repo=self.message_repo,
            quarantine_engine=self.quarantine_engine,
            schema_validator=self.schema_validator,
        )

        self.cache_manager = cache_manager or CacheManager()

        self.user_lookup = UserLookupService(self.user_repo, self.summary_repo)
        self.channel_lookup = ChannelLookupService(self.group_repo, self.business_repo, self.user_repo, self.history_repo)
        self.history_lookup = HistoryLookupService(self.history_repo, self.event_repo, self.summary_repo)

        self._is_initialized: bool = False

    def initialize(self, dataset_dir: Optional[str] = None) -> None:
        """Initialize data layer components and execute 7-stage boot pipeline."""
        target_dir = dataset_dir or self.dataset_dir
        logger.info("Initializing DataManager facade", dataset_dir=target_dir)

        result = self.data_loader.execute_pipeline(target_dir)
        self._is_initialized = True
        logger.info("DataManager initialized successfully", boot_summary=result)

    def reload(self) -> None:
        """Reload dataset repositories and purge cache tiers."""
        logger.info("Reloading DataManager data repositories")
        self.cache_manager.purge_all()
        self.user_repo.clear()
        self.group_repo.clear()
        self.business_repo.clear()
        self.media_repo.clear()
        self.history_repo.clear()
        self.event_repo.clear()
        self.summary_repo.clear()
        self.message_repo.clear()

        self.data_loader.execute_pipeline(self.dataset_dir)
        logger.info("DataManager reload completed successfully")

    def shutdown(self) -> None:
        """Gracefully shutdown DataManager and release resources."""
        logger.info("Shutting down DataManager")
        self.cache_manager.purge_all()
        self.user_repo.clear()
        self.group_repo.clear()
        self.business_repo.clear()
        self.media_repo.clear()
        self.history_repo.clear()
        self.event_repo.clear()
        self.summary_repo.clear()
        self.message_repo.clear()
        self._is_initialized = False

    def get_status(self) -> Mapping[str, Any]:
        """Return data layer status, health metrics, and repository record counts."""
        return {
            "initialized": self._is_initialized,
            "status": "healthy" if self._is_initialized else "uninitialized",
            "counts": {
                "users": self.user_repo.count(),
                "groups": self.group_repo.count(),
                "businesses": self.business_repo.count(),
                "history_messages": self.history_repo.count(),
                "events": self.event_repo.count(),
                "summaries": self.summary_repo.count(),
                "messages": self.message_repo.count(),
            },
            "quarantined_records": len(self.quarantine_engine.get_quarantined()),
        }
