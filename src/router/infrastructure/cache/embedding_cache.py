"""Embedding Cache Infrastructure as specified in embedding_retrieval.md."""

import hashlib
import logging
from collections import OrderedDict

from router.domain.ports.retrieval_ports import IEmbeddingCache

logger = logging.getLogger(__name__)


class EmbeddingCache(IEmbeddingCache):
    """Two-tier embedding cache for document vectors and query vector LRU cache."""

    def __init__(self, max_lru_size: int = 1000) -> None:
        """Initialize EmbeddingCache.

        Args:
            max_lru_size: Maximum capacity for in-memory query LRU cache.
        """
        self._max_lru_size = max_lru_size
        self._query_lru_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._document_embedding_store: dict[str, list[float]] = {}
        self._hits = 0
        self._misses = 0
        logger.info("EmbeddingCache initialized with LRU capacity %d", max_lru_size)

    def _hash_key(self, text: str) -> str:
        """Compute MD5 hash key for normalized string."""
        normalized = text.strip().lower()
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get_query_embedding(self, query_text: str) -> list[float] | None:
        """Retrieve query vector from LRU cache.

        Args:
            query_text: Raw or normalized query text.

        Returns:
            Cached float vector or None if cache miss.
        """
        key = self._hash_key(query_text)
        if key in self._query_lru_cache:
            self._hits += 1
            self._query_lru_cache.move_to_end(key)
            logger.debug("Query embedding LRU cache hit for key %s", key)
            return self._query_lru_cache[key]
        self._misses += 1
        return None

    def put_query_embedding(self, query_text: str, vector: list[float]) -> None:
        """Store query vector in LRU cache.

        Args:
            query_text: Raw or normalized query text.
            vector: 384-dimensional dense vector.
        """
        key = self._hash_key(query_text)
        if key in self._query_lru_cache:
            self._query_lru_cache.move_to_end(key)
        self._query_lru_cache[key] = vector
        if len(self._query_lru_cache) > self._max_lru_size:
            self._query_lru_cache.popitem(last=False)
        logger.debug("Stored query vector in LRU cache for key %s", key)

    def get_document_embedding(self, message_id: str) -> list[float] | None:
        """Retrieve pre-computed document vector by historical message ID."""
        return self._document_embedding_store.get(message_id)

    def put_document_embedding(self, message_id: str, vector: list[float]) -> None:
        """Store pre-computed document vector for historical message ID."""
        self._document_embedding_store[message_id] = vector

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def clear(self) -> None:
        """Clear LRU and document caches."""
        self._query_lru_cache.clear()
        self._document_embedding_store.clear()
        self._hits = 0
        self._misses = 0
