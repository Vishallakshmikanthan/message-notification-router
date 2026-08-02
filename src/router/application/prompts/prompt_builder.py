"""Prompt Builder — dynamic context injection and prompt assembly.

Assembles the full prompt payload from versioned templates and runtime signals,
injecting all required variables into template placeholders.

Responsibilities:
- Load the appropriate prompt template via PromptLoader.
- Inject runtime context variables (signals, evidence, message).
- Apply context compression via ContextCompressor.
- Encode signals compactly via TokenOptimizer.
- Report cache eligibility for provider prefix caching.

Spec: prompt_architecture.md §2 (Prompt Layer Architectural Specifications).
      prompt_architecture.md §3 (Context Window Management & Token Optimization).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from router.application.prompts.context_compressor import ContextCompressor
from router.application.prompts.prompt_cache import PromptCache
from router.application.prompts.prompt_loader import PromptLoader, PromptNotFoundError
from router.application.prompts.prompt_version import PromptVersion
from router.application.prompts.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


@dataclass
class BuiltPrompt:
    """Assembled prompt payload ready for LLM dispatch.

    Attributes:
        system_prompt: Static system directive (eligible for provider caching).
        user_prompt: Dynamic user turn containing compressed context + message.
        version: PromptVersion of the templates used.
        estimated_tokens: Estimated total input token count.
        is_cache_hit: Whether the system prompt was a prefix cache hit.
        system_fingerprint: SHA-256 fingerprint of the system prompt.
        api_params: LLM API call parameters (max_tokens, temperature).
    """

    system_prompt: str
    user_prompt: str
    version: PromptVersion
    estimated_tokens: int
    is_cache_hit: bool
    system_fingerprint: str
    api_params: dict[str, Any]

    @property
    def full_text(self) -> str:
        """Combined system + user prompt for single-string providers."""
        return f"{self.system_prompt}\n\n{self.user_prompt}"

    def __repr__(self) -> str:
        return (
            f"BuiltPrompt(version={self.version.full_id!r}, "
            f"tokens~={self.estimated_tokens}, "
            f"cache_hit={self.is_cache_hit})"
        )


class PromptBuilder:
    """Dynamic prompt assembler with context injection.

    Combines versioned YAML templates with runtime signal data to produce
    optimized, compressed prompts ready for LLM dispatch.

    Args:
        loader: PromptLoader for YAML template access.
        compressor: ContextCompressor for token budget management.
        optimizer: TokenOptimizer for signal encoding and API params.
        cache: PromptCache for system prefix hit tracking.
        provider: LLM provider name for cache key scoping.
        major_version: Prompt template major version to load (default 1).
    """

    def __init__(
        self,
        loader: PromptLoader | None = None,
        compressor: ContextCompressor | None = None,
        optimizer: TokenOptimizer | None = None,
        cache: PromptCache | None = None,
        provider: str = "default",
        major_version: int = 1,
    ) -> None:
        """Initialize PromptBuilder with all sub-components.

        Args:
            loader: Prompt template loader.
            compressor: Context compression engine.
            optimizer: Token optimizer.
            cache: System prefix cache.
            provider: LLM provider identifier.
            major_version: Template major version.
        """
        self._loader = loader or PromptLoader()
        self._compressor = compressor or ContextCompressor()
        self._optimizer = optimizer or TokenOptimizer()
        self._cache = cache or PromptCache()
        self._provider = provider
        self._major_version = major_version
        logger.info(
            "PromptBuilder initialized",
            extra={"provider": provider, "major_version": major_version},
        )

    def build_classification_prompt(
        self,
        message_text: str,
        signal_dict: dict[str, Any],
        evidence_snippets: list[str] | None = None,
        thread_turns: list[str] | None = None,
        few_shot_examples: list[str] | None = None,
    ) -> BuiltPrompt:
        """Build the full Tier 1 classification prompt.

        Assembles: system_prompt + (few_shot) + (context) + classification_prompt.

        Args:
            message_text: Incoming message content.
            signal_dict: Computed signal key-value pairs.
            evidence_snippets: Retrieved RAG evidence strings.
            thread_turns: Historical conversation turns.
            few_shot_examples: Dynamic few-shot exemplar strings.

        Returns:
            BuiltPrompt ready for LLM dispatch.
        """
        return self._build(
            prompt_id="classification_prompt",
            message_text=message_text,
            signal_dict=signal_dict,
            evidence_snippets=evidence_snippets or [],
            thread_turns=thread_turns or [],
            few_shot_examples=few_shot_examples or [],
        )

    def build_reasoning_prompt(
        self,
        message_text: str,
        signal_dict: dict[str, Any],
        evidence_snippets: list[str] | None = None,
        thread_turns: list[str] | None = None,
    ) -> BuiltPrompt:
        """Build the Tier 2 multi-stage reasoning prompt.

        Args:
            message_text: Incoming message content.
            signal_dict: Computed signal key-value pairs.
            evidence_snippets: Retrieved RAG evidence strings.
            thread_turns: Historical conversation turns.

        Returns:
            BuiltPrompt with reasoning CoT structure.
        """
        return self._build(
            prompt_id="reasoning_prompt",
            message_text=message_text,
            signal_dict=signal_dict,
            evidence_snippets=evidence_snippets or [],
            thread_turns=thread_turns or [],
        )

    def build_repair_prompt(
        self,
        malformed_response: str,
        schema_errors: list[str],
    ) -> BuiltPrompt:
        """Build the Stage 4 output repair prompt (max 200 tokens).

        Args:
            malformed_response: Raw malformed LLM response string.
            schema_errors: List of schema validation error messages.

        Returns:
            BuiltPrompt for the repair call.
        """
        system_template = self._load_system()
        repair_template = self._loader.load("output_validation_prompt", self._major_version)

        variables: dict[str, Any] = {
            "malformed_response": malformed_response[:500],
            "schema_errors": "\n".join(f"- {e}" for e in schema_errors[:5]),
        }
        user_prompt = repair_template.render(variables)
        system_prompt = system_template.raw_content

        is_hit, fingerprint = self._cache.check(self._provider, system_prompt)
        if not is_hit:
            self._cache.store(
                self._provider,
                system_prompt,
                system_template.version.prompt_id,
                system_template.version.version_string,
            )

        return BuiltPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            version=repair_template.version,
            estimated_tokens=self._optimizer.estimate_tokens(system_prompt + user_prompt),
            is_cache_hit=is_hit,
            system_fingerprint=fingerprint,
            api_params={**self._optimizer.build_api_params(), "max_tokens": 200},
        )

    def _build(
        self,
        prompt_id: str,
        message_text: str,
        signal_dict: dict[str, Any],
        evidence_snippets: list[str] | None = None,
        thread_turns: list[str] | None = None,
        few_shot_examples: list[str] | None = None,
    ) -> BuiltPrompt:
        """Internal prompt assembly pipeline.

        Args:
            prompt_id: Template identifier to load.
            message_text: Message content.
            signal_dict: Signal dictionary.
            evidence_snippets: Evidence strings.
            thread_turns: Thread history.
            few_shot_examples: Few-shot exemplars.

        Returns:
            BuiltPrompt assembly.
        """
        system_template = self._load_system()
        task_template = self._loader.load(prompt_id, self._major_version)

        # Compress context sections
        compressed = self._compressor.compress(
            system_text=system_template.raw_content,
            message_text=message_text,
            signal_dict=signal_dict,
            rag_snippets=evidence_snippets,
            thread_turns=thread_turns,
            few_shot_examples=few_shot_examples,
        )

        # Build template variables
        variables = self._build_variables(signal_dict, evidence_snippets or [], message_text)

        # Render the task prompt with variable injection
        try:
            user_prompt = task_template.render(variables)
        except Exception:
            # Fallback: use compressed message if template render fails
            logger.warning(
                "Template render failed; using compressed message fallback",
                extra={"prompt_id": prompt_id},
            )
            user_prompt = compressed.message_text

        system_prompt = compressed.system_text

        # Check / update prefix cache
        is_hit, fingerprint = self._cache.check(self._provider, system_prompt)
        if not is_hit:
            self._cache.store(
                self._provider,
                system_prompt,
                system_template.version.prompt_id,
                system_template.version.version_string,
            )

        estimated_tokens = self._optimizer.estimate_tokens(system_prompt + user_prompt)

        logger.info(
            "Prompt built",
            extra={
                "prompt_id": prompt_id,
                "version": task_template.version.version_string,
                "estimated_tokens": estimated_tokens,
                "is_cache_hit": is_hit,
                "compression_ratio": compressed.compression_ratio,
            },
        )

        return BuiltPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            version=task_template.version,
            estimated_tokens=estimated_tokens,
            is_cache_hit=is_hit,
            system_fingerprint=fingerprint,
            api_params=self._optimizer.build_api_params(),
        )

    def _load_system(self):
        """Load the system prompt template.

        Returns:
            PromptTemplate for the system_prompt.
        """
        try:
            return self._loader.load("system_prompt", self._major_version)
        except PromptNotFoundError:
            logger.warning("system_prompt.yaml not found; using inline fallback")
            from router.application.prompts.prompt_loader import PromptTemplate
            version = PromptVersion(
                major=1, minor=0, patch=0, prompt_id="system_prompt", layer="system"
            )
            return PromptTemplate(
                version=version,
                raw_content=(
                    "You are an expert AI notification routing engine. "
                    "Output ONLY valid JSON. No markdown, no prose."
                ),
                token_budget=400,
                cacheable=True,
                description="Inline fallback system prompt",
            )

    @staticmethod
    def _build_variables(
        signal_dict: dict[str, Any],
        evidence_snippets: list[str],
        message_text: str,
    ) -> dict[str, Any]:
        """Build template variable substitution dict.

        Args:
            signal_dict: Signal key-value pairs.
            evidence_snippets: Evidence snippet strings.
            message_text: Raw message text.

        Returns:
            Variable dict for template rendering.
        """
        evidence_formatted = "\n".join(
            f"[{i + 1}] {s}" for i, s in enumerate(evidence_snippets[:5])
        ) if evidence_snippets else "No evidence retrieved."

        return {
            "message_text": message_text[:800],
            "evidence_snippets": evidence_formatted,
            "urgency_score": signal_dict.get("urgency_score", 0.5),
            "spam_score": signal_dict.get("spam_score", 0.0),
            "trust_score": signal_dict.get("trust_score", 0.5),
            "relationship_closeness": signal_dict.get("relationship_closeness", 0.5),
            "is_quiet_hours": signal_dict.get("is_quiet_hours", False),
            "user_activity_status": signal_dict.get("user_activity_status", "UNKNOWN"),
            "sender_is_vip": signal_dict.get("sender_is_vip", False),
            "sender_in_address_book": signal_dict.get("sender_in_address_book", False),
            "notification_fatigue_score": signal_dict.get("notification_fatigue_score", 0.5),
            "media_type": signal_dict.get("media_type", "NONE"),
            "message_type": signal_dict.get("message_type", "UNKNOWN"),
            "hour_of_day": signal_dict.get("hour_of_day", 12),
            # For classification prompt
            "proposed_action": signal_dict.get("proposed_action", "DELIVER_SILENTLY"),
            "action": signal_dict.get("action", "DELIVER_SILENTLY"),
            "reason": signal_dict.get("reason", ""),
            "confidence": signal_dict.get("confidence", 0.5),
            "signal_completeness": signal_dict.get("signal_completeness", 0.5),
            "evidence_count": len(evidence_snippets),
            "conflicting_signals": signal_dict.get("conflicting_signals", False),
            "evidence_keys": str(signal_dict.get("evidence_keys", [])),
            # For repair prompt (defaults; overridden in build_repair_prompt)
            "malformed_response": "",
            "schema_errors": "",
        }
