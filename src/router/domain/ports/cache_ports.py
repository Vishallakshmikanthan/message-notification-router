"""Abstract Cache Port Specifications for Domain & Application Layer."""

from abc import ABC, abstractmethod
from typing import Any


class ICache(ABC):
    """Abstract Single Cache Tier Interface."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        ...

    @abstractmethod
    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Put value in cache with optional TTL."""
        ...

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Invalidate cached entry by key."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all entries in tier."""
        ...


class ICacheManager(ABC):
    """Abstract Multi-Tier Cache Manager Interface."""

    @abstractmethod
    def get(self, tier: str, key: str) -> Any | None:
        """Get cached value from specific tier."""
        ...

    @abstractmethod
    def put(self, tier: str, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value into specific cache tier."""
        ...

    @abstractmethod
    def invalidate(self, tier: str, key: str) -> None:
        """Invalidate key in specific tier."""
        ...

    @abstractmethod
    def purge_all(self) -> None:
        """Purge all cache tiers."""
        ...
