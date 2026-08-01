"""StringInternPool implementation to optimize memory overhead of repeated strings."""

import sys


class StringInternPool:
    """Pools and re-uses identical string pointers in RAM."""

    def __init__(self) -> None:
        """Initialize intern pool mapping."""
        self._pool: dict[str, str] = {}

    def intern(self, raw_string: str) -> str:
        """Return canonical interned string pointer."""
        if not isinstance(raw_string, str):
            return raw_string
        if raw_string in self._pool:
            return self._pool[raw_string]
        interned = sys.intern(raw_string)
        self._pool[raw_string] = interned
        return interned

    def clear(self) -> None:
        """Clear intern pool reference cache."""
        self._pool.clear()
