"""Multi-Tier CacheManager Implementation conforming to cache_strategy.md."""

from collections import OrderedDict
import time
from typing import Any, Dict, Optional

from router.core.logging.logger import get_logger
from router.domain.ports.cache_ports import ICache, ICacheManager

logger = get_logger(__name__)


class InMemoryCacheTier(ICache):
    """In-memory LRU/TTL cache tier implementation."""

    def __init__(self, name: str, max_capacity: Optional[int] = None, default_ttl: Optional[int] = None) -> None:
        """Initialize cache tier store with optional max capacity and default TTL."""
        self.name = name
        self.max_capacity = max_capacity
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._expiry: Dict[str, float] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value by key, enforcing TTL expiration and LRU ordering."""
        if key not in self._store:
            return None

        # Check TTL
        if key in self._expiry and time.time() > self._expiry[key]:
            self.invalidate(key)
            return None

        # Move to end for LRU
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Put value into cache tier, evicting LRU entry if capacity exceeded."""
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value

        if effective_ttl is not None:
            self._expiry[key] = time.time() + effective_ttl

        # Evict LRU if capacity exceeded
        if self.max_capacity and len(self._store) > self.max_capacity:
            oldest_key, _ = self._store.popitem(last=False)
            self._expiry.pop(oldest_key, None)

    def invalidate(self, key: str) -> None:
        """Invalidate cache entry by key."""
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    def clear(self) -> None:
        """Clear all entries in cache tier."""
        self._store.clear()
        self._expiry.clear()

    def size(self) -> int:
        """Return current entry count."""
        return len(self._store)


class CacheManager(ICacheManager):
    """Orchestrates 4 cache tiers (Static, Lookup, History, Media)."""

    def __init__(self) -> None:
        """Initialize 4 standard cache tiers specified in cache_strategy.md."""
        self._tiers: dict[str, InMemoryCacheTier] = {
            "static": InMemoryCacheTier("static"),  # Tier 1: Immutable zero eviction
            "lookup": InMemoryCacheTier("lookup", max_capacity=1000),  # Tier 2: LRU capacity 1000
            "history": InMemoryCacheTier("history", default_ttl=300),  # Tier 3: TTL 300s
            "media": InMemoryCacheTier("media"),  # Tier 4: Disk verification bitset
        }
        self._requests: int = 0
        self._hits: int = 0
        self._misses: int = 0

    def get(self, tier: str, key: str) -> Any | None:
        """Get cached value from specific tier and track telemetry."""
        self._requests += 1
        cache_tier = self._tiers.get(tier)
        if not cache_tier:
            self._misses += 1
            return None

        val = cache_tier.get(key)
        if val is not None:
            self._hits += 1
        else:
            self._misses += 1
        return val

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

    def get_stats(self) -> Dict[str, Any]:
        """Return cache manager operational stats and hit ratios."""
        hit_ratio = (self._hits / self._requests * 100.0) if self._requests > 0 else 0.0
        return {
            "total_requests": self._requests,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio_percent": round(hit_ratio, 2),
            "tier_sizes": {name: tier.size() for name, tier in self._tiers.items()},
        }
