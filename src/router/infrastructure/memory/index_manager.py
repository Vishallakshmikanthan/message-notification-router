"""IndexManager implementation for managing composite hash keys and secondary indexes."""

from typing import Any


class IndexManager:
    """Constructs and maintains primary, composite, and inverted indexes using fast bit-shifting hash arithmetic."""

    @staticmethod
    def build_tuple_key(key1: str, key2: str) -> tuple[str, str]:
        """Build composite tuple hash key."""
        return (key1, key2)

    @staticmethod
    def compute_composite_hash(key1: str, key2: str) -> int:
        """Compute bit-shifting composite hash: ((hash(key1) * 31) ^ hash(key2))."""
        return ((hash(key1) * 31) ^ hash(key2))

    @staticmethod
    def build_secondary_index(items: list[Any], key_extractor: Any) -> dict[str, list[Any]]:
        """Construct inverted secondary index mapping keys to lists of entities."""
        index: dict[str, list[Any]] = {}
        for item in items:
            k = key_extractor(item)
            if k is not None:
                if k not in index:
                    index[k] = []
                index[k].append(item)
        return index

    @staticmethod
    def build_set_index(items: list[Any], tuple_extractor: Any) -> set[tuple[str, str]]:
        """Construct fast O(1) set index of composite key tuples."""
        index: set[tuple[str, str]] = set()
        for item in items:
            t = tuple_extractor(item)
            if t is not None:
                index.add(t)
        return index
