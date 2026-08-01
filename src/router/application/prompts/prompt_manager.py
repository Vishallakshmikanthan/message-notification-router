"""Prompt Manager — central registry for versioned prompt templates.

The PromptManager is the single authoritative entry point for all prompt
interactions in the system. It coordinates the PromptLoader, PromptCache,
PromptBuilder, ContextCompressor, and TokenOptimizer into a unified interface.

Spec: prompt_architecture.md §6 (Prompt Engineering Governance & Version Control).
- Prompts stored in centralized directory under Semantic Versioning.
- Every execution records prompt_id, prompt_version for full observability.
- CI/CD automated prompt assertion suites run against this manager.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from router.application.prompts.context_compressor import ContextCompressor
from router.application.prompts.prompt_builder import BuiltPrompt, PromptBuilder
from router.application.prompts.prompt_cache import PromptCache, CacheStats
from router.application.prompts.prompt_loader import PromptLoader, PromptTemplate
from router.application.prompts.prompt_version import PromptVersion
from router.application.prompts.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class PromptManager:
    """Central prompt registry and orchestration facade.

    Provides a clean, versioned interface for building prompts across all
    pipeline layers without exposing internal YAML loading or caching details.

    All prompt builds are logged with prompt_id and version for full audit trails.

    Args:
        provider: LLM provider name (e.g., 'anthropic', 'openai', 'default').
        major_version: Prompt template major version to use (default 1).
        loader: Optional custom PromptLoader (for testing / custom paths).
        cache: Optional custom PromptCache (for testing).
    """

    def __init__(
        self,
        provider: str = "default",
        major_version: int = 1,
        loader: Optional[PromptLoader] = None,
        cache: Optional[PromptCache] = None,
    ) -> None:
        """Initialize the PromptManager.

        Args:
            provider: LLM provider name.
            major_version: Template major version.
            loader: Custom PromptLoader (optional).
            cache: Custom PromptCache (optional).
        """
        self._provider = provider
        self._major_version = major_version
        self._loader = loader or PromptLoader()
        self._cache = cache or PromptCache()
        self._optimizer = TokenOptimizer()
        self._compressor = ContextCompressor()
        self._builder = PromptBuilder(
            loader=self._loader,
            compressor=self._compressor,
            optimizer=self._optimizer,
            cache=self._cache,
            provider=provider,
            major_version=major_version,
        )
        logger.info(
            "PromptManager initialized",
            extra={"provider": provider, "major_version": major_version},
        )

    # ------------------------------------------------------------------
    # Public prompt build API
    # ------------------------------------------------------------------

    def build_classification(
        self,
        message_text: str,
        signal_dict: Dict[str, Any],
        evidence_snippets: Optional[List[str]] = None,
        thread_turns: Optional[List[str]] = None,
        few_shot_examples: Optional[List[str]] = None,
    ) -> BuiltPrompt:
        """Build a Tier 1 fast-path classification prompt.

        Args:
            message_text: Incoming notification text.
            signal_dict: Computed signal key-value pairs.
            evidence_snippets: Retrieved RAG evidence strings.
            thread_turns: Historical conversation turns.
            few_shot_examples: Dynamic few-shot exemplars.

        Returns:
            BuiltPrompt ready for provider dispatch.
        """
        prompt = self._builder.build_classification_prompt(
            message_text=message_text,
            signal_dict=signal_dict,
            evidence_snippets=evidence_snippets,
            thread_turns=thread_turns,
            few_shot_examples=few_shot_examples,
        )
        self._log_build("classification_prompt", prompt)
        return prompt

    def build_reasoning(
        self,
        message_text: str,
        signal_dict: Dict[str, Any],
        evidence_snippets: Optional[List[str]] = None,
        thread_turns: Optional[List[str]] = None,
    ) -> BuiltPrompt:
        """Build a Tier 2 multi-stage chain-of-thought reasoning prompt.

        Args:
            message_text: Incoming notification text.
            signal_dict: Computed signal key-value pairs.
            evidence_snippets: Retrieved RAG evidence strings.
            thread_turns: Historical conversation turns.

        Returns:
            BuiltPrompt with reasoning scaffold.
        """
        prompt = self._builder.build_reasoning_prompt(
            message_text=message_text,
            signal_dict=signal_dict,
            evidence_snippets=evidence_snippets,
            thread_turns=thread_turns,
        )
        self._log_build("reasoning_prompt", prompt)
        return prompt

    def build_repair(
        self,
        malformed_response: str,
        schema_errors: List[str],
    ) -> BuiltPrompt:
        """Build the Stage 4 output repair / self-healing prompt.

        Args:
            malformed_response: Raw malformed LLM response string.
            schema_errors: List of detected schema validation errors.

        Returns:
            BuiltPrompt for the repair LLM call (max 200 output tokens).
        """
        prompt = self._builder.build_repair_prompt(malformed_response, schema_errors)
        self._log_build("output_validation_prompt", prompt)
        return prompt

    # ------------------------------------------------------------------
    # Template inspection API
    # ------------------------------------------------------------------

    def get_template(self, prompt_id: str) -> PromptTemplate:
        """Retrieve a raw PromptTemplate by ID.

        Args:
            prompt_id: Prompt identifier (e.g., 'system_prompt').

        Returns:
            PromptTemplate instance.

        Raises:
            PromptNotFoundError: If the template does not exist.
        """
        return self._loader.load(prompt_id, self._major_version)

    def list_available_prompts(self) -> List[str]:
        """List all available prompt IDs for the current major version.

        Returns:
            List of prompt identifiers.
        """
        templates_dir = self._loader._template_dir / f"v{self._major_version}"
        if not templates_dir.exists():
            return []
        return [p.stem for p in templates_dir.glob("*.yaml")]

    def get_version_info(self, prompt_id: str) -> PromptVersion:
        """Get the PromptVersion for a specific template.

        Args:
            prompt_id: Prompt identifier.

        Returns:
            PromptVersion descriptor.
        """
        template = self._loader.load(prompt_id, self._major_version)
        return template.version

    # ------------------------------------------------------------------
    # Cache and observability API
    # ------------------------------------------------------------------

    def get_cache_stats(self) -> Dict[str, CacheStats]:
        """Return prompt prefix cache statistics.

        Returns:
            Dict mapping provider → CacheStats.
        """
        return self._cache.get_stats()

    def invalidate_cache(self, prompt_id: Optional[str] = None) -> None:
        """Invalidate the prompt template loader cache.

        Args:
            prompt_id: If provided, invalidate only this template.
                       If None, flush all cached templates.
        """
        self._loader.invalidate_cache(prompt_id)
        logger.info(
            "PromptManager: template cache invalidated",
            extra={"prompt_id": prompt_id or "ALL"},
        )

    def get_token_budget(self) -> Dict[str, int]:
        """Return the current token budget allocation.

        Returns:
            Dict mapping section name → token budget.
        """
        budget = self._optimizer.budget
        return {
            "system": budget.system_tokens,
            "few_shot": budget.few_shot_tokens,
            "context": budget.context_tokens,
            "message": budget.message_tokens,
            "completion": budget.completion_tokens,
            "total_input": budget.total_input_tokens,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_build(prompt_id: str, prompt: BuiltPrompt) -> None:
        """Log prompt build for observability audit trail.

        Args:
            prompt_id: Prompt identifier.
            prompt: Built prompt result.
        """
        logger.info(
            "Prompt built",
            extra={
                "prompt_id": prompt_id,
                "prompt_version": prompt.version.version_string,
                "estimated_tokens": prompt.estimated_tokens,
                "is_cache_hit": prompt.is_cache_hit,
                "system_fingerprint": prompt.system_fingerprint[:16],
            },
        )
