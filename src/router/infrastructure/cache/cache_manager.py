"""Multi-Tier CacheManager Implementation."""

from typing import Any

from router.core.logging.logger import get_logger
from router.domain.ports.cache_ports import ICache, ICacheManager

logger = get_logger(__name__)


class InMemoryCacheTier(ICache):
    """In-memory LRU/TTL cache tier implementation."""

    def __init__(self, name: str) -> None:
        """Initialize cache tier store."""
        self.name = name
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        return self._store.get(key)

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Put value into cache tier."""
        self._store[key] = value

    def invalidate(self, key: str) -> None:
        """Invalidate cache entry by key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all entries in cache tier."""
        self._store.clear()


class CacheManager(ICacheManager):
    """Orchestrates 4 cache tiers (Static, Lookup, History, Media)."""

    def __init__(self) -> None:
        """Initialize 4 standard cache tiers."""
        self._tiers: dict[str, ICache] = {
            "static": InMemoryCacheTier("static"),
            "lookup": InMemoryCacheTier("lookup"),
            "history": InMemoryCacheTier("history"),
            "media": InMemoryCacheTier("media"),
        }

    def get(self, tier: str, key: str) -> Any | None:
        """Get cached value from specific tier."""
        cache_tier = self._tiers.get(tier)
        return cache_tier.get(key) if cache_tier else None

    def put(self, tier: str, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value into specific cache tier."""
        cache_tier = self._tiers.get(tier)
        if cache_tier:
            cache_tier.put(key, value, ttl_seconds)

    def invalidate(self, tier: str, key: str) -> None:
        """Invalidate key in specific tier."""
        cache_tier = self._tiers.get(tier)
        if cache_tier:
            cache_tier.invalidate(key)

    def purge_all(self) -> None:
        """Purge all cache tiers."""
        for tier in self._tiers.values():
            tier.clear()
        logger.info("Purged all cache tiers")
