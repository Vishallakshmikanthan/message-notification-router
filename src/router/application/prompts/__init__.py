"""Prompts package — versioned prompt template system.

Exposes the core prompt management API for the WhatsApp Notification Router:
- PromptManager: Central registry and build orchestrator.
- PromptBuilder: Dynamic context injection and assembly.
- PromptLoader: YAML template loader with caching.
- PromptCache: System prefix caching for provider efficiency.
- ContextCompressor: 4,096-token budget management.
- TokenOptimizer: Compact signal encoding.
- PromptVersion: Immutable semantic version descriptors.
"""

from router.application.prompts.context_compressor import CompressedContext, ContextCompressor
from router.application.prompts.prompt_builder import BuiltPrompt, PromptBuilder
from router.application.prompts.prompt_cache import CacheStats, PromptCache, PromptCacheEntry
from router.application.prompts.prompt_loader import (
    PromptLoader,
    PromptLoadError,
    PromptNotFoundError,
    PromptTemplate,
)
from router.application.prompts.prompt_manager import PromptManager
from router.application.prompts.prompt_version import PromptVersion
from router.application.prompts.token_optimizer import TokenBudgetAllocation, TokenOptimizer

__all__ = [
    # Manager
    "PromptManager",
    # Builder
    "PromptBuilder",
    "BuiltPrompt",
    # Loader
    "PromptLoader",
    "PromptTemplate",
    "PromptNotFoundError",
    "PromptLoadError",
    # Cache
    "PromptCache",
    "PromptCacheEntry",
    "CacheStats",
    # Compressor
    "ContextCompressor",
    "CompressedContext",
    # Optimizer
    "TokenOptimizer",
    "TokenBudgetAllocation",
    # Version
    "PromptVersion",
]
