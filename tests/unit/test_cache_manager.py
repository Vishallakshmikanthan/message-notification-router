"""Unit tests for multi-tier CacheManager LRU, TTL, and telemetry stats."""

import time
from router.infrastructure.cache.cache_manager import CacheManager, InMemoryCacheTier


def test_lru_cache_tier_eviction() -> None:
    """Verify LRU capacity eviction in cache tier."""
    tier = InMemoryCacheTier("lookup", max_capacity=2)
    tier.put("k1", "val1")
    tier.put("k2", "val2")
    tier.put("k3", "val3")  # Evicts k1

    assert tier.get("k1") is None
    assert tier.get("k2") == "val2"
    assert tier.get("k3") == "val3"


def test_ttl_cache_tier_expiration() -> None:
    """Verify TTL expiration in cache tier."""
    tier = InMemoryCacheTier("history", default_ttl=1)
    tier.put("k1", "val1")
    assert tier.get("k1") == "val1"

    time.sleep(1.1)
    assert tier.get("k1") is None


def test_cache_manager_telemetry() -> None:
    """Verify CacheManager stats tracking."""
    cm = CacheManager()
    cm.put("lookup", "key1", "data1")

    assert cm.get("lookup", "key1") == "data1"
    assert cm.get("lookup", "key_missing") is None

    stats = cm.get_stats()
    assert stats["total_requests"] == 2
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_ratio_percent"] == 50.0
