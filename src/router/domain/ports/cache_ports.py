"""Abstract cache port definitions."""

from abc import ABC, abstractmethod


class CachePort(ABC):
    """Abstract interface contract for high-speed caching operations."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Retrieve a cached string value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Store a string value in cache with a time-to-live expiration."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        pass
