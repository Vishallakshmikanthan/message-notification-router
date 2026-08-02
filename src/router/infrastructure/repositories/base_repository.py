"""Base Repository Generic Concrete Implementation."""

from collections.abc import Sequence
from typing import Generic, TypeVar

from router.domain.ports.repository_ports import IRepository

TEntity = TypeVar("TEntity")
TKey = TypeVar("TKey")


class BaseRepository(IRepository[TEntity, TKey], Generic[TEntity, TKey]):
    """In-memory thread-safe thread-lock-free Base Repository implementation."""

    def __init__(self) -> None:
        """Initialize in-memory primary index dictionary."""
        self._store: dict[TKey, TEntity] = {}

    def get_by_id(self, key: TKey) -> TEntity | None:
        """Perform O(1) primary key lookup."""
        return self._store.get(key)

    def get_all(self) -> Sequence[TEntity]:
        """Return read-only collection of all entities."""
        return list(self._store.values())

    def exists(self, key: TKey) -> bool:
        """Evaluate key presence in O(1) time."""
        return key in self._store

    def count(self) -> int:
        """Return total number of managed records."""
        return len(self._store)

    def add(self, key: TKey, entity: TEntity) -> None:
        """Add or replace entity in primary index store."""
        self._store[key] = entity

    def clear(self) -> None:
        """Clear repository storage."""
        self._store.clear()
