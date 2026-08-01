"""LLMInterface — Structured LLM ReasoningService wrapping the AI inference call.

Design principles:
- No raw prompt strings are exposed or hardcoded in this module.
- All input and output are strictly typed dataclasses.
- Implements a 5-step internal reasoning process as specified in decision_engine.md §5.
- Fallback is triggered on timeout (>250ms) or API errors.
- Production systems plug in a real LLM backend (Gemini, OpenAI) via constructor injection.

Spec: decision_engine.md §5 LLM Reasoner Architecture.
     decision_flow.md Stage 7: LLM Reasoner Execution.
     llm_strategy.md §2 Tier 1: Fast Single-Pass Router.
"""

from __future__ import annotations

import time
from typing import List, Optional

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    DecisionAction,
    DecisionCategory,
    ReasonerInputFrame,
    ReasoningOutput,
)
from router.domain.ports.decision_ports import ILLMInterface

logger = get_logger(__name__)

_LLM_TIMEOUT_MS = 250.0
"""Maximum allowed LLM invocation latency in milliseconds (decision_flow.md Stage 7)."""

_REASONING_SUMMARY_MAX_CHARS = 250
"""Maximum characters for reasoning_summary output (decision_engine.md §5)."""


class LLMTimeoutError(Exception):
    """Raised when LLM invocation exceeds the 250ms SLA budget."""


class LLMServiceError(Exception):
    """Raised when the LLM service returns an unexpected error or invalid payload."""


class LLMInterface(ILLMInterface):
    """Structured LLM Reasoning Service.

    Wraps a backend LLM callable (injected via constructor) and exposes
    a typed `reason()` method. The backend callable receives a
    ReasonerInputFrame dict and returns a dict matching the ReasoningOutput schema.

    If no backend is injected, the AnalyticReasoningEngine (deterministic
    heuristic reasoner) is used as the default. This guarantees zero external
    dependency for unit tests and local development.

    Args:
        backend: Optional callable(dict) -> dict. If None, uses the built-in
                 AnalyticReasoningEngine.
        timeout_ms: LLM response timeout budget in milliseconds (default 250ms).
    """

    def __init__(
        self,
        backend: Optional[callable] = None,
        timeout_ms: float = _LLM_TIMEOUT_MS,
    ) -> None:
        """Initialize LLMInterface with optional external backend.

        Args:
            backend: Callable accepting input_dict and returning output_dict.
                     If None, the built-in heuristic reasoner is used.
            timeout_ms: Timeout budget in milliseconds.
        """
        self._backend = backend
        self._timeout_ms = timeout_ms
        self._analytic_reasoner = AnalyticReasoningEngine()
        logger.info(
            "LLMInterface initialized",
            has_external_backend=backend is not None,
            timeout_ms=timeout_ms,
        )

    def reason(self, frame: ReasonerInputFrame) -> ReasoningOutput:
        """Invoke the LLM reasoner with a structured context frame.

        Implements the 5-step reasoning process:
          Step 1: Parse Input Context Frame.
          Step 2: Social & Safety Alignment.
          Step 3: Temporal & User State Evaluation.
          Step 4: Evidence Grounding Check.
          Step 5: Action Synthesis & Score Generation.

        Args:
            frame: Typed input frame with message payload, signals, and evidence.

        Returns:
            Structured ReasoningOutput with proposed action and rationale.

        Raises:
            LLMTimeoutError: If invocation exceeds timeout_ms.
            LLMServiceError: If the backend returns an invalid payload structure.
        """
        start_time = time.perf_counter()

        try:
            if self._backend is not None:
                output = self._invoke_external_backend(frame, start_time)
            else:
                output = self._analytic_reasoner.reason(frame)

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if latency_ms > self._timeout_ms:
                logger.warning(
                    "LLM invocation exceeded SLA timeout",
                    latency_ms=round(latency_ms, 2),
                    timeout_ms=self._timeout_ms,
                )
                raise LLMTimeoutError(
                    f"LLM exceeded {self._timeout_ms}ms SLA (actual: {latency_ms:.1f}ms)"
                )

            logger.info(
                "LLM reasoning completed",
                proposed_action=output.proposed_action,
                raw_confidence=round(output.raw_confidence, 3),
                latency_ms=round(latency_ms, 2),
            )

            # Return a new instance with the latency populated
            return ReasoningOutput(
                proposed_action=output.proposed_action,
                urgency_rating=output.urgency_rating,
                importance_rating=output.importance_rating,
                reasoning_summary=output.reasoning_summary[:_REASONING_SUMMARY_MAX_CHARS],
                key_factors=output.key_factors,
                raw_confidence=output.raw_confidence,
                proposed_category=output.proposed_category,
                evidence_ids_referenced=output.evidence_ids_referenced,
                llm_latency_ms=latency_ms,
            )

        except LLMTimeoutError:
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                "LLM reasoning failure",
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )
            raise LLMServiceError(f"LLM backend error: {exc}") from exc

    def _invoke_external_backend(
        self, frame: ReasonerInputFrame, start_time: float
    ) -> ReasoningOutput:
        """Invoke the external LLM backend and parse its output.

        Args:
            frame: Typed ReasonerInputFrame.
            start_time: Perf counter start for timeout check.

        Returns:
            Parsed ReasoningOutput from the backend.

        Raises:
            LLMServiceError: If backend output is missing required fields.
        """
        input_dict = {
            "message_text": frame.message_text,
            "message_type": frame.message_type,
            "urgency_score": frame.urgency_score,
            "spam_score": frame.spam_score,
            "trust_score": frame.trust_score,
            "relationship_closeness": frame.relationship_closeness,
            "is_quiet_hours": frame.is_quiet_hours,
            "user_activity_status": frame.user_activity_status,
            "sender_is_vip": frame.sender_is_vip,
            "sender_in_address_book": frame.sender_in_address_book,
            "hour_of_day": frame.hour_of_day,
            "evidence_snippets": [
                {
                    "id": e.evidence_id,
                    "text": e.text_snippet,
                    "relevance": e.relevance_score,
                }
                for e in frame.evidence_snippets
            ],
        }

        result = self._backend(input_dict)

        if not isinstance(result, dict):
            raise LLMServiceError("Backend returned non-dict response.")

        required_fields = [
            "proposed_action",
            "urgency_rating",
            "importance_rating",
            "reasoning_summary",
            "key_factors",
            "raw_confidence",
        ]
        missing = [f for f in required_fields if f not in result]
        if missing:
            raise LLMServiceError(f"Backend response missing fields: {missing}")

        try:
            action = DecisionAction(result["proposed_action"])
        except ValueError:
            raise LLMServiceError(
                f"Invalid proposed_action enum value: {result['proposed_action']}"
            )

        try:
            category_str = result.get("proposed_category", "PERSONAL_CASUAL")
            category = DecisionCategory(category_str)
        except ValueError:
            category = DecisionCategory.PERSONAL_CASUAL

        evidence_ids = result.get("evidence_ids_referenced", [])

        return ReasoningOutput(
            proposed_action=action,
            urgency_rating=float(result["urgency_rating"]),
            importance_rating=float(result["importance_rating"]),
            reasoning_summary=str(result["reasoning_summary"])[:_REASONING_SUMMARY_MAX_CHARS],
            key_factors=list(result["key_factors"]),
            raw_confidence=float(result["raw_confidence"]),
            proposed_category=category,
            evidence_ids_referenced=evidence_ids,
        )


# ---------------------------------------------------------------------------
# AnalyticReasoningEngine — built-in heuristic reasoner (no LLM required)
# ---------------------------------------------------------------------------


class AnalyticReasoningEngine:
    """Deterministic heuristic reasoner used when no external LLM backend is configured.

    Implements a rule-of-thumb scoring function that approximates LLM reasoning
    using the signal scores already available in the ReasonerInputFrame.

    This is the production fallback and is also used in unit tests for
    deterministic, reproducible outputs without API calls.

    Not intended to replace LLM reasoning — designed as a graceful degradation path.
    """

    def reason(self, frame: ReasonerInputFrame) -> ReasoningOutput:
        """Apply heuristic multi-signal synthesis to produce a ReasoningOutput.

        Implements the 5-step reasoning process:
          Step 1: Parse signals.
          Step 2: Social & Safety Alignment (spam/trust checks).
          Step 3: Temporal & User State Evaluation.
          Step 4: Evidence Grounding Check.
          Step 5: Action Synthesis.

        Args:
            frame: Typed ReasonerInputFrame.

        Returns:
            Deterministic ReasoningOutput derived from signal heuristics.
        """
        # Step 2: Safety check
        if frame.spam_score > 0.80:
            return self._build_output(
                action=DecisionAction.SUPPRESS_SPAM,
                category=DecisionCategory.SPAM_VIRAL,
                urgency=frame.urgency_score,
                importance=0.1,
                confidence=0.85,
                summary="High spam probability detected; message suppressed.",
                key_factors=["HIGH_SPAM_SCORE"],
                evidence_ids=self._evidence_ids(frame),
            )

        # Step 3: Temporal & user state
        if frame.is_quiet_hours and not frame.sender_is_vip and frame.urgency_score < 0.85:
            return self._build_output(
                action=DecisionAction.DELIVER_SILENT,
                category=DecisionCategory.PERSONAL_CASUAL,
                urgency=frame.urgency_score,
                importance=0.4,
                confidence=0.82,
                summary="Quiet hours active; message delivered silently.",
                key_factors=["QUIET_HOURS_ACTIVE", "NON_VIP_SENDER"],
                evidence_ids=self._evidence_ids(frame),
            )

        # Step 4: Evidence grounding check
        has_grounded_evidence = any(
            e.relevance_score >= 0.6 for e in frame.evidence_snippets
        )

        # Step 5: Action synthesis
        if frame.urgency_score >= 0.80:
            action = DecisionAction.DELIVER_IMMEDIATELY
            category = DecisionCategory.PERSONAL_URGENT
            summary = "High urgency detected; immediate delivery warranted."
            key_factors = self._urgency_factors(frame)
            confidence = 0.82 if has_grounded_evidence else 0.72
            importance = 0.85

        elif frame.urgency_score >= 0.55:
            if frame.sender_in_address_book:
                action = DecisionAction.DELIVER_SILENT
                category = DecisionCategory.PERSONAL_CASUAL
                summary = "Moderate urgency from known contact; silent delivery."
                key_factors = ["KNOWN_CONTACT", "MODERATE_URGENCY"]
                confidence = 0.74
            else:
                action = DecisionAction.SUMMARIZE_LATER
                category = DecisionCategory.PERSONAL_CASUAL
                summary = "Moderate urgency from unknown sender; schedule summary."
                key_factors = ["UNKNOWN_SENDER", "MODERATE_URGENCY"]
                confidence = 0.68
            importance = 0.55

        elif frame.trust_score >= 0.70:
            action = DecisionAction.DELIVER_SILENT
            category = DecisionCategory.PERSONAL_CASUAL
            summary = "High trust sender with low urgency; delivered silently."
            key_factors = ["HIGH_TRUST_SCORE", "LOW_URGENCY"]
            confidence = 0.72
            importance = 0.45

        else:
            action = DecisionAction.SUMMARIZE_LATER
            category = DecisionCategory.PERSONAL_CASUAL
            summary = "Low urgency and unknown context; added to summary queue."
            key_factors = ["LOW_URGENCY", "SPARSE_CONTEXT"]
            confidence = 0.60
            importance = 0.30

        return self._build_output(
            action=action,
            category=category,
            urgency=frame.urgency_score,
            importance=importance,
            confidence=confidence,
            summary=summary,
            key_factors=key_factors,
            evidence_ids=self._evidence_ids(frame),
        )

    @staticmethod
    def _build_output(
        action: DecisionAction,
        category: DecisionCategory,
        urgency: float,
        importance: float,
        confidence: float,
        summary: str,
        key_factors: List[str],
        evidence_ids: List[str],
    ) -> ReasoningOutput:
        return ReasoningOutput(
            proposed_action=action,
            urgency_rating=min(1.0, max(0.0, urgency)),
            importance_rating=min(1.0, max(0.0, importance)),
            reasoning_summary=summary[:_REASONING_SUMMARY_MAX_CHARS],
            key_factors=key_factors,
            raw_confidence=min(0.97, max(0.10, confidence)),
            proposed_category=category,
            evidence_ids_referenced=evidence_ids,
        )

    @staticmethod
    def _urgency_factors(frame: ReasonerInputFrame) -> List[str]:
        """Derive key_factors list from urgency signal values."""
        factors: List[str] = []
        if frame.urgency_score >= 0.90:
            factors.append("CRITICAL_URGENCY")
        if frame.sender_is_vip:
            factors.append("VIP_CONTACT")
        if frame.sender_in_address_book:
            factors.append("KNOWN_CONTACT")
        if frame.has_media:
            factors.append("MEDIA_ATTACHMENT")
        return factors or ["HIGH_URGENCY"]

    @staticmethod
    def _evidence_ids(frame: ReasonerInputFrame) -> List[str]:
        """Extract evidence IDs from the top evidence snippets."""
        return [e.evidence_id for e in frame.evidence_snippets if e.relevance_score >= 0.5]
