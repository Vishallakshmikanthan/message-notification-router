"""DataManager implementation implementing IDataManager interface contract."""

from typing import Any, Mapping

from router.core.logging.logger import get_logger
from router.domain.ports.cache_ports import ICacheManager
from router.domain.ports.service_ports import IDataLoader, IDataManager
from router.infrastructure.cache.cache_manager import CacheManager
from router.infrastructure.storage.data_loader import DataLoader

logger = get_logger(__name__)


class DataManager(IDataManager):
    """Central Data Layer facade and sub-system lifecycle manager."""

    def __init__(
        self,
        data_loader: IDataLoader | None = None,
        cache_manager: ICacheManager | None = None,
    ) -> None:
        """Initialize DataManager dependencies."""
        self.data_loader = data_loader or DataLoader()
        self.cache_manager = cache_manager or CacheManager()
        self._is_initialized: bool = False

    def initialize(self, dataset_dir: str) -> None:
        """Initialize data layer components and execute boot pipeline."""
        logger.info("Initializing DataManager facade", dataset_dir=dataset_dir)
        self.data_loader.execute_pipeline(dataset_dir)
        self._is_initialized = True
        logger.info("DataManager initialized successfully")

    def reload(self) -> None:
        """Reload dataset repositories and purge cache tiers."""
        logger.info("Reloading DataManager data repositories")
        self.cache_manager.purge_all()

    def shutdown(self) -> None:
        """Gracefully shutdown DataManager and release resources."""
        logger.info("Shutting down DataManager")
        self.cache_manager.purge_all()
        self._is_initialized = False

    def get_status(self) -> Mapping[str, Any]:
        """Return data layer status and health metrics."""
        return {
            "initialized": self._is_initialized,
            "status": "healthy" if self._is_initialized else "uninitialized",
        }
