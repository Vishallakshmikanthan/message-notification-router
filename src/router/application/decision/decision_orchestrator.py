"""DecisionOrchestrator — controls evaluation branching and builds the LLM input frame.

Responsibilities:
- Constructs a structured ReasonerInputFrame from DecisionContext.
- Injects top-5 evidence snippets for factual grounding.
- Provides temporal context, sender relationship tier, and user activity status.
- Does NOT execute any LLM calls itself.

Spec: decision_engine.md §3 Decision Orchestration, decision_flow.md Stage 6.
"""

from __future__ import annotations

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    DecisionContext,
    EvidenceSnippet,
    ReasonerInputFrame,
)
from router.domain.entities.evidence import EvidenceItem
from router.domain.ports.decision_ports import IDecisionOrchestrator

logger = get_logger(__name__)

_MAX_EVIDENCE_SNIPPETS = 5
_MAX_SNIPPET_TEXT_LENGTH = 300  # Characters per snippet to keep frame compact


class DecisionOrchestrator(IDecisionOrchestrator):
    """Constructs the structured prompt-free input frame for the LLM ReasoningService.

    Design principles:
    - No raw prompt strings: all data passed as typed fields.
    - Evidence injection limited to top-5 snippets by relevance score.
    - All scores are normalized floats (0.0–1.0).
    - User activity status derived from signal heuristics.
    """

    def prepare_reasoner_frame(self, context: DecisionContext) -> ReasonerInputFrame:
        """Construct the structured LLM input frame from the DecisionContext.

        Applies:
        1. Evidence snippet extraction (top-5 by relevance).
        2. Signal aggregation into normalized float scalars.
        3. Temporal and user activity context injection.
        4. Sender relationship tier resolution.

        Args:
            context: Validated DecisionContext.

        Returns:
            Typed ReasonerInputFrame consumed by LLMInterface.
        """
        mc = context.message_context
        sb = context.signal_bundle
        eb = context.evidence_bundle

        # -- Core message fields ------------------------------------------
        message_text = mc.message_text or mc.core_message.cleaned_text or ""
        message_type = mc.core_message.message_type
        language_code = mc.receiver.preferred_language if mc.receiver else "en"
        char_count = mc.core_message.char_count

        # -- Signals -------------------------------------------------------
        urgency_score = sb.urgency_score
        spam_score = sb.risk.spam.score
        trust_score = sb.trust.relationship_score.score
        relationship_closeness = sb.trust.known_contact_score.score
        sentiment_score = sb.trust.historical_trust.score  # proxy for sentiment

        # -- User / quiet hours context -----------------------------------
        is_quiet_hours = sb.is_quiet_hours
        user_activity_status = self._infer_activity_status(context)

        # -- Sender relationship ------------------------------------------
        sender_is_vip = trust_score >= 0.85
        sender_in_address_book = sb.personal_sender_known
        sender_relationship_type = self._resolve_relationship_type(context)

        # -- Temporal context ----------------------------------------------
        temporal = mc.temporal_info
        local_time_iso = temporal.iso_timestamp
        day_of_week = temporal.day_of_week
        hour_of_day = temporal.hour_of_day

        # -- Evidence snippets (top-5) -------------------------------------
        evidence_snippets = self._extract_evidence_snippets(eb)

        # -- Media context ------------------------------------------------
        media_ctx = context.media_context
        has_media = False
        media_type_str = "TEXT_ONLY"
        media_summary = ""
        media_risk_score = 0.0

        if media_ctx:
            if hasattr(media_ctx, "has_media"):
                has_media = media_ctx.has_media
            if hasattr(media_ctx, "media_type"):
                media_type_str = media_ctx.media_type
            if hasattr(media_ctx, "image_summary"):
                media_summary = media_ctx.image_summary or ""
            if hasattr(media_ctx, "image_risk_score"):
                media_risk_score = media_ctx.image_risk_score or 0.0

        # -- Historical context -------------------------------------------
        hist_response_latency = 0.0
        missed_calls = 0
        hist_open_rate = 0.0

        if context.historical_context:
            hc = context.historical_context
            if hasattr(hc, "days_since_last_interaction"):
                hist_response_latency = hc.days_since_last_interaction * 86400.0
        hist_open_rate = sb.history.historical_open_rate.score

        frame = ReasonerInputFrame(
            message_text=message_text[:500],  # Truncate to 500 chars
            message_type=message_type,
            language_code=language_code,
            char_count=char_count,
            urgency_score=urgency_score,
            spam_score=spam_score,
            trust_score=trust_score,
            relationship_closeness=relationship_closeness,
            sentiment_score=sentiment_score,
            is_quiet_hours=is_quiet_hours,
            user_activity_status=user_activity_status,
            sender_is_vip=sender_is_vip,
            sender_in_address_book=sender_in_address_book,
            sender_relationship_type=sender_relationship_type,
            local_time_iso=local_time_iso,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            evidence_snippets=evidence_snippets,
            has_media=has_media,
            media_type=media_type_str,
            media_summary=media_summary,
            media_risk_score=media_risk_score,
            historical_response_latency_seconds=hist_response_latency,
            missed_calls_from_sender=missed_calls,
            historical_open_rate=hist_open_rate,
        )

        logger.info(
            "ReasonerInputFrame prepared",
            context_id=context.context_id,
            urgency_score=round(urgency_score, 3),
            trust_score=round(trust_score, 3),
            evidence_count=len(evidence_snippets),
            has_media=has_media,
            sender_is_vip=sender_is_vip,
        )

        return frame

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_evidence_snippets(eb) -> list[EvidenceSnippet]:
        """Extract top-5 evidence snippets ordered by similarity score.

        Args:
            eb: EvidenceBundle containing retrieved items.

        Returns:
            List of up to 5 EvidenceSnippet objects.
        """
        items: list[EvidenceItem] = sorted(
            eb.items, key=lambda e: e.similarity_score, reverse=True
        )[:_MAX_EVIDENCE_SNIPPETS]

        snippets: list[EvidenceSnippet] = []
        for item in items:
            snippet_text = (item.raw_text or "")[:_MAX_SNIPPET_TEXT_LENGTH]
            snippets.append(
                EvidenceSnippet(
                    evidence_id=item.message_id,
                    text_snippet=snippet_text,
                    relevance_score=item.similarity_score,
                    source_type=item.source_dataset,
                )
            )
        return snippets

    @staticmethod
    def _infer_activity_status(context: DecisionContext) -> str:
        """Infer user activity status from temporal signals and notification context.

        Heuristic rules:
        - SLEEPING: quiet hours active during night hours (22:00–06:00).
        - IN_MEETING: working hours AND notification fatigue HIGH.
        - DRIVING: not used without explicit GPS signal (fallback AVAILABLE).
        - AVAILABLE: default.

        Args:
            context: DecisionContext.

        Returns:
            Activity status string: AVAILABLE, IN_MEETING, SLEEPING.
        """
        sb = context.signal_bundle
        hour = context.message_context.temporal_info.hour_of_day

        if sb.is_quiet_hours and (hour >= 22 or hour < 6):
            return "SLEEPING"

        fatigue = sb.behaviour.notification_fatigue.score
        if context.message_context.temporal_info.is_working_hours and fatigue > 0.70:
            return "IN_MEETING"

        return "AVAILABLE"

    @staticmethod
    def _resolve_relationship_type(context: DecisionContext) -> str:
        """Resolve human-readable relationship type from RelationshipContext.

        Args:
            context: DecisionContext.

        Returns:
            Relationship type string from RelationshipContext or fallback.
        """
        rel = context.message_context.relationship
        if rel:
            return rel.relationship_type
        return "UNKNOWN"
