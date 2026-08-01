"""Retrieval Cache Infrastructure for caching EvidenceBundle payloads."""

import hashlib
import logging
import time
from typing import Dict, Optional, Tuple

from router.domain.entities.evidence import EvidenceBundle
from router.domain.ports.retrieval_ports import IRetrievalCache

logger = logging.getLogger(__name__)


class RetrievalCache(IRetrievalCache):
    """Caches EvidenceBundle instances with TTL eviction."""

    def __init__(self) -> None:
        """Initialize RetrievalCache store."""
        self._store: Dict[str, Tuple[EvidenceBundle, float]] = {}
        self._hits = 0
        self._misses = 0
        logger.info("RetrievalCache initialized")

    def build_cache_key(self, query_message_id: str, user_id: str, message_text: str) -> str:
        """Construct MD5 hash cache key."""
        raw_key = f"{query_message_id}:{user_id}:{message_text.strip().lower()}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def get_bundle(self, cache_key: str) -> Optional[EvidenceBundle]:
        """Retrieve cached EvidenceBundle if key exists and TTL is valid."""
        if cache_key in self._store:
            bundle, expire_at = self._store[cache_key]
            if time.time() < expire_at:
                self._hits += 1
                logger.debug("Retrieval cache hit for key %s", cache_key)
                return bundle
            else:
                logger.debug("Retrieval cache expired key %s", cache_key)
                del self._store[cache_key]
        self._misses += 1
        return None

    def put_bundle(self, cache_key: str, bundle: EvidenceBundle, ttl_seconds: int = 300) -> None:
        """Store EvidenceBundle with expiration TTL."""
        expire_at = time.time() + ttl_seconds
        self._store[cache_key] = (bundle, expire_at)
        logger.debug("Stored EvidenceBundle in retrieval cache key %s (TTL=%ds)", cache_key, ttl_seconds)

    def clear(self) -> None:
        """Clear cache store."""
        self._store.clear()
        self._hits = 0
        self._misses = 0
