"""Prompt Cache — in-process prefix caching for system prompt tokens.

Implements the L4 Provider Prompt Cache strategy from performance.md §3:
- Fixed System Directives and static schemas are positioned at the prompt head.
- The system prefix fingerprint is tracked per provider (Anthropic, OpenAI).
- Cache hit ratio is tracked via a simple counter for telemetry export.

This cache does NOT call the LLM provider — it manages the system prefix
string and reports whether the current invocation can benefit from provider
prefix caching (i.e., the system prompt is identical to the previous call).

Spec: performance.md §3 (L4 Provider Prompt Cache, 85-90% hit rate).
      prompt_architecture.md §3 (Prompt Prefix Caching).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Tracks prompt cache hit/miss statistics for telemetry.

    Attributes:
        hits: Number of cache hits (identical system prefix reused).
        misses: Number of cache misses (new system prefix generated).
        total_requests: Total number of cache lookups.
    """

    hits: int = 0
    misses: int = 0
    total_requests: int = 0

    @property
    def hit_ratio(self) -> float:
        """Compute hit ratio as float in [0.0, 1.0].

        Returns:
            Hit ratio or 0.0 if no requests yet.
        """
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1
        self.total_requests += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
        self.total_requests += 1

    def reset(self) -> None:
        """Reset all counters."""
        self.hits = 0
        self.misses = 0
        self.total_requests = 0


@dataclass
class PromptCacheEntry:
    """Cached system prefix entry keyed by content fingerprint.

    Attributes:
        fingerprint: SHA-256 hash of the system prompt content.
        system_prompt: The actual system prompt string.
        prompt_id: Identifier of the source prompt template.
        version: Semantic version string (e.g., "1.0.0").
    """

    fingerprint: str
    system_prompt: str
    prompt_id: str
    version: str


class PromptCache:
    """In-process prefix cache for system prompt reuse tracking.

    Tracks which system prompt was last sent to each provider and reports
    whether the current invocation is a cache hit (identical prefix) or miss.

    Provider-level prefix caching is vendor-managed (Anthropic cache_control,
    OpenAI prompt caching). This class manages the fingerprint comparison
    logic to enable that feature on the client side.

    Args:
        max_entries: Maximum number of cached entries per provider (default 32).
    """

    def __init__(self, max_entries: int = 32) -> None:
        """Initialize PromptCache.

        Args:
            max_entries: Maximum cache entries per provider.
        """
        self._max_entries = max_entries
        # Keyed by provider name → {fingerprint: PromptCacheEntry}
        self._entries: dict[str, dict[str, PromptCacheEntry]] = {}
        self._stats: dict[str, CacheStats] = {}
        logger.info("PromptCache initialized", extra={"max_entries": max_entries})

    def check(self, provider: str, system_prompt: str) -> tuple[bool, str]:
        """Check whether the given system prompt is cached for the provider.

        Records a hit if the fingerprint matches the last seen entry,
        or a miss if it is new.

        Args:
            provider: LLM provider name (e.g., "anthropic", "openai").
            system_prompt: The full system prompt string to check.

        Returns:
            Tuple of (is_cache_hit: bool, fingerprint: str).
        """
        fingerprint = self._hash(system_prompt)
        stats = self._get_stats(provider)
        provider_cache = self._entries.get(provider, {})

        is_hit = fingerprint in provider_cache
        if is_hit:
            stats.record_hit()
            logger.debug(
                "Prompt cache HIT",
                extra={"provider": provider, "fingerprint": fingerprint[:16]},
            )
        else:
            stats.record_miss()
            logger.debug(
                "Prompt cache MISS",
                extra={"provider": provider, "fingerprint": fingerprint[:16]},
            )

        return is_hit, fingerprint

    def store(
        self,
        provider: str,
        system_prompt: str,
        prompt_id: str,
        version: str,
    ) -> str:
        """Store a system prompt in the cache for the given provider.

        Evicts the oldest entry if the cache is at capacity.

        Args:
            provider: LLM provider name.
            system_prompt: System prompt string to cache.
            prompt_id: Prompt template identifier.
            version: Semantic version string.

        Returns:
            Fingerprint hash of the stored entry.
        """
        fingerprint = self._hash(system_prompt)
        if provider not in self._entries:
            self._entries[provider] = {}

        provider_cache = self._entries[provider]

        if fingerprint not in provider_cache:
            # Evict oldest if at capacity
            if len(provider_cache) >= self._max_entries:
                oldest_key = next(iter(provider_cache))
                del provider_cache[oldest_key]
                logger.debug(
                    "PromptCache evicted entry",
                    extra={"provider": provider, "evicted_key": oldest_key[:16]},
                )

            provider_cache[fingerprint] = PromptCacheEntry(
                fingerprint=fingerprint,
                system_prompt=system_prompt,
                prompt_id=prompt_id,
                version=version,
            )
            logger.debug(
                "PromptCache stored",
                extra={
                    "provider": provider,
                    "prompt_id": prompt_id,
                    "version": version,
                    "fingerprint": fingerprint[:16],
                },
            )

        return fingerprint

    def get_entry(self, provider: str, fingerprint: str) -> PromptCacheEntry | None:
        """Retrieve a cached entry by fingerprint.

        Args:
            provider: LLM provider name.
            fingerprint: SHA-256 fingerprint hash.

        Returns:
            PromptCacheEntry or None if not cached.
        """
        return self._entries.get(provider, {}).get(fingerprint)

    def get_stats(self, provider: str | None = None) -> dict[str, CacheStats]:
        """Return cache statistics per provider.

        Args:
            provider: If provided, return stats only for this provider.

        Returns:
            Dict mapping provider name → CacheStats.
        """
        if provider is not None:
            return {provider: self._get_stats(provider)}
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset all hit/miss counters."""
        for stats in self._stats.values():
            stats.reset()

    def _get_stats(self, provider: str) -> CacheStats:
        """Get or create stats tracker for a provider."""
        if provider not in self._stats:
            self._stats[provider] = CacheStats()
        return self._stats[provider]

    @staticmethod
    def _hash(content: str) -> str:
        """Compute a SHA-256 fingerprint of a string.

        Args:
            content: String to hash.

        Returns:
            Lowercase hex SHA-256 digest.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
