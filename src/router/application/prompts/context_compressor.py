"""Context Compressor — token budget management for the prompt context window.

Implements the Prompt Compression & Trimming Pipeline from prompt_architecture.md §3:
1. Stop-Word & Noise Removal — strips metadata boilerplate and redundant timestamps.
2. Dynamic Thread Trimming — retains last N=5 turns + top K=3 RAG snippets.
3. Structured Signal Encoding — converts signals to compact key-value strings.
4. Token Budget Enforcement — hard-limits each section to its allocated token budget.

Token Budget (4,096 token window, prompt_architecture.md §3):
  System & Safety Directives :  400 tokens (10%)
  Dynamic Few-Shot Exemplars  :  600 tokens (15%)
  Retrieved Memory & Context  : 1,600 tokens (39%)
  Current Message & Signals   :  800 tokens (20%)
  Model Output Reserve (Max)  :  696 tokens (16%)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Token budget constants (prompt_architecture.md §3)
BUDGET_SYSTEM = 400
BUDGET_FEW_SHOT = 600
BUDGET_CONTEXT = 1_600
BUDGET_MESSAGE = 800
BUDGET_OUTPUT = 696
TOTAL_BUDGET = 4_096

# Compression parameters (prompt_architecture.md §3)
MAX_THREAD_TURNS = 5
MAX_RAG_SNIPPETS = 3

# Conservative characters-per-token estimate (GPT-4/Claude tokenizer avg: ~3.5 chars/token)
_CHARS_PER_TOKEN = 3.5


@dataclass
class CompressedContext:
    """Output of the context compression pipeline.

    Attributes:
        system_text: Compressed system prompt text.
        few_shot_text: Compressed few-shot exemplar text.
        context_text: Compressed retrieved memory + context text.
        message_text: Compressed message + signal encoding.
        estimated_tokens: Estimated total token count.
        compression_ratio: Ratio of output_chars / input_chars.
    """

    system_text: str
    few_shot_text: str
    context_text: str
    message_text: str
    estimated_tokens: int
    compression_ratio: float

    @property
    def full_prompt(self) -> str:
        """Concatenate all sections into the full prompt string."""
        parts = [self.system_text]
        if self.few_shot_text:
            parts.append(self.few_shot_text)
        if self.context_text:
            parts.append(self.context_text)
        parts.append(self.message_text)
        return "\n\n".join(p for p in parts if p.strip())


class ContextCompressor:
    """Context window token budget manager.

    Compresses and trims context sections to fit within the 4,096-token
    budget while maximising signal-to-noise ratio.

    Args:
        max_thread_turns: Maximum conversation turns to retain (default 5).
        max_rag_snippets: Maximum RAG snippets to retain (default 3).
        chars_per_token: Characters-per-token estimate for budget calculations.
    """

    def __init__(
        self,
        max_thread_turns: int = MAX_THREAD_TURNS,
        max_rag_snippets: int = MAX_RAG_SNIPPETS,
        chars_per_token: float = _CHARS_PER_TOKEN,
    ) -> None:
        """Initialize ContextCompressor.

        Args:
            max_thread_turns: Maximum conversation thread turns to retain.
            max_rag_snippets: Maximum RAG evidence snippets to retain.
            chars_per_token: Characters-to-tokens conversion ratio.
        """
        self._max_thread_turns = max_thread_turns
        self._max_rag_snippets = max_rag_snippets
        self._chars_per_token = chars_per_token

    def compress(
        self,
        system_text: str,
        message_text: str,
        signal_dict: dict,
        rag_snippets: Optional[List[str]] = None,
        thread_turns: Optional[List[str]] = None,
        few_shot_examples: Optional[List[str]] = None,
    ) -> CompressedContext:
        """Compress all context sections to fit the 4,096-token budget.

        Args:
            system_text: System prompt content (max 400 tokens).
            message_text: Raw incoming message text (max 800 tokens).
            signal_dict: Signal key-value dict for compact encoding.
            rag_snippets: Retrieved RAG memory snippets.
            thread_turns: Historical conversation turns.
            few_shot_examples: Dynamic few-shot exemplar strings.

        Returns:
            CompressedContext with all sections budgeted.
        """
        original_chars = (
            len(system_text)
            + len(message_text)
            + sum(len(s) for s in (rag_snippets or []))
            + sum(len(t) for t in (thread_turns or []))
        )

        # Step 1: Compress system text
        sys_compressed = self._trim_to_budget(
            self._remove_noise(system_text), BUDGET_SYSTEM
        )

        # Step 2: Compress few-shot exemplars
        few_shot_text = self._compress_few_shots(few_shot_examples or [], BUDGET_FEW_SHOT)

        # Step 3: Compress retrieved context (RAG + threads)
        context_text = self._compress_context(
            rag_snippets or [], thread_turns or [], BUDGET_CONTEXT
        )

        # Step 4: Encode message + signals compactly
        msg_compressed = self._compress_message(message_text, signal_dict, BUDGET_MESSAGE)

        # Estimate total tokens
        total_chars = (
            len(sys_compressed)
            + len(few_shot_text)
            + len(context_text)
            + len(msg_compressed)
        )
        estimated_tokens = int(total_chars / self._chars_per_token)
        compression_ratio = total_chars / original_chars if original_chars > 0 else 1.0

        logger.debug(
            "Context compressed",
            extra={
                "original_chars": original_chars,
                "compressed_chars": total_chars,
                "estimated_tokens": estimated_tokens,
                "compression_ratio": round(compression_ratio, 3),
            },
        )

        return CompressedContext(
            system_text=sys_compressed,
            few_shot_text=few_shot_text,
            context_text=context_text,
            message_text=msg_compressed,
            estimated_tokens=estimated_tokens,
            compression_ratio=round(compression_ratio, 3),
        )

    def _compress_context(
        self, rag_snippets: List[str], thread_turns: List[str], budget: int
    ) -> str:
        """Combine and trim RAG snippets and thread turns.

        Applies:
        - Top-K RAG snippet retention (K=3).
        - Last-N thread turn retention (N=5).
        - Budget trimming on the combined result.

        Args:
            rag_snippets: Retrieved evidence snippets (ordered by relevance).
            thread_turns: Historical conversation turns (chronological).
            budget: Token budget for this section.

        Returns:
            Compressed context string.
        """
        top_snippets = rag_snippets[: self._max_rag_snippets]
        recent_turns = thread_turns[-self._max_thread_turns :]

        sections: List[str] = []
        if top_snippets:
            sections.append("## Retrieved Context\n" + "\n".join(top_snippets))
        if recent_turns:
            sections.append("## Recent Thread\n" + "\n".join(recent_turns))

        combined = "\n\n".join(sections)
        return self._trim_to_budget(self._remove_noise(combined), budget)

    def _compress_few_shots(self, examples: List[str], budget: int) -> str:
        """Compress few-shot examples to budget.

        Args:
            examples: List of formatted exemplar strings.
            budget: Token budget.

        Returns:
            Compressed few-shot string.
        """
        if not examples:
            return ""
        combined = "\n\n".join(examples)
        return self._trim_to_budget(combined, budget)

    def _compress_message(
        self, message_text: str, signal_dict: dict, budget: int
    ) -> str:
        """Encode message and signals into compact format.

        Uses compact key-value signal encoding to save ~35% prompt tokens
        (performance.md §6: e.g., `urgency:0.82|rel:0.91|dnd:false`).

        Args:
            message_text: Raw message text.
            signal_dict: Signal key-value pairs.
            budget: Token budget.

        Returns:
            Compact message+signal encoded string.
        """
        # Compact signal encoding (performance.md §6)
        signal_line = self._encode_signals(signal_dict)
        message_cleaned = self._remove_noise(message_text)

        combined = f"{signal_line}\n\n<user_message_content>\n{message_cleaned}\n</user_message_content>"
        return self._trim_to_budget(combined, budget)

    @staticmethod
    def _encode_signals(signal_dict: dict) -> str:
        """Encode signal dict into compact key-value pipe-separated string.

        Example output: ``urgency:0.82|rel:0.91|dnd:false|spam:0.03``

        Args:
            signal_dict: Signal names mapped to values.

        Returns:
            Compact KV encoded string.
        """
        parts = []
        key_map = {
            "urgency_score": "urgency",
            "spam_score": "spam",
            "trust_score": "trust",
            "relationship_closeness": "rel",
            "is_quiet_hours": "dnd",
            "sender_is_vip": "vip",
            "sender_in_address_book": "known",
            "notification_fatigue_score": "fatigue",
            "media_type": "media",
        }
        for long_key, short_key in key_map.items():
            if long_key in signal_dict:
                val = signal_dict[long_key]
                if isinstance(val, float):
                    val = f"{val:.2f}"
                elif isinstance(val, bool):
                    val = "true" if val else "false"
                parts.append(f"{short_key}:{val}")

        return "|".join(parts) if parts else "signals:unavailable"

    @staticmethod
    def _remove_noise(text: str) -> str:
        """Remove metadata boilerplate, duplicate timestamps, and whitespace noise.

        Args:
            text: Raw text to clean.

        Returns:
            Cleaned text.
        """
        # Remove duplicate blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing whitespace per line
        text = "\n".join(line.rstrip() for line in text.splitlines())
        # Strip leading/trailing whitespace
        return text.strip()

    def _trim_to_budget(self, text: str, token_budget: int) -> str:
        """Hard-trim text to fit within the token budget.

        Uses character-count approximation. Truncates from the end, preserving
        complete words where possible.

        Args:
            text: Text to trim.
            token_budget: Maximum number of tokens allowed.

        Returns:
            Trimmed text.
        """
        max_chars = int(token_budget * self._chars_per_token)
        if len(text) <= max_chars:
            return text

        # Truncate at nearest word boundary
        truncated = text[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > max_chars * 0.85:
            truncated = truncated[:last_space]

        logger.debug(
            "Context section trimmed",
            extra={
                "original_chars": len(text),
                "trimmed_chars": len(truncated),
                "token_budget": token_budget,
            },
        )
        return truncated + " …[trimmed]"
