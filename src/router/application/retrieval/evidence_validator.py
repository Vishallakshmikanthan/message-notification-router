"""Evidence Validation Pipeline implementing 5 Validation Gates from evidence_models.md."""

import logging
import re
from typing import List, Set

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import RetrievalCandidate
from router.domain.ports.retrieval_ports import IEvidenceValidator

logger = logging.getLogger(__name__)


class EvidenceValidator(IEvidenceValidator):
    """Executes 5 quality gates on candidate pool before evidence bundle assembly."""

    def __init__(self) -> None:
        """Initialize EvidenceValidator."""
        logger.info("EvidenceValidator initialized")

    def validate_candidates(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Execute 5 validation gates on candidate pool.

        Args:
            candidates: Re-ranked top-10 candidate pool.
            context: Current MessageContext.

        Returns:
            Validated collection of candidates.
        """
        if not candidates:
            return []

        # Gate 1: False Positive Removal (Domain Entity Contradictions)
        g1_candidates = self._gate1_false_positive_filter(candidates, context)

        # Gate 2: Duplicate Evidence Suppression (24-hour window)
        g2_candidates = self._gate2_duplicate_suppression(g1_candidates)

        # Gate 3: Quality & Relevance Thresholding (score >= 0.35 or exact match)
        g3_candidates = self._gate3_quality_thresholding(g2_candidates, context)

        # Gate 4: Conflicting Evidence Resolution
        g4_candidates = self._gate4_conflict_resolution(g3_candidates, context)

        # Gate 5: Cold Start & Sparse History Handling
        validated = self._gate5_cold_start_handler(g4_candidates, context)

        logger.debug("Validated %d candidates out of original %d", len(validated), len(candidates))
        return validated

    def _gate1_false_positive_filter(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Gate 1: Remove candidates where semantic score is high but entity codes contradict."""
        query_text = context.message_text or ""
        query_numbers = set(re.findall(r"\b\d{4,8}\b", query_text))

        filtered: List[RetrievalCandidate] = []
        for cand in candidates:
            msg_text = cand.historical_message.message_text if cand.historical_message else ""
            msg_numbers = set(re.findall(r"\b\d{4,8}\b", msg_text))

            # Contradiction check: if query has OTP/order digits and msg has DIFFERENT digits
            if query_numbers and msg_numbers and not query_numbers.intersection(msg_numbers):
                if cand.dense_score > 0.80 and cand.bm25_score == 0:
                    logger.debug("Gate 1 dropped candidate %s due to entity contradiction", cand.message_id)
                    continue
            filtered.append(cand)
        return filtered

    def _gate2_duplicate_suppression(
        self, candidates: List[RetrievalCandidate]
    ) -> List[RetrievalCandidate]:
        """Gate 2: Suppress near-duplicate items from same sender within 24-hour window."""
        seen_senders_24h: Set[str] = set()
        suppressed: List[RetrievalCandidate] = []

        for cand in candidates:
            sender = cand.historical_message.sender_id if cand.historical_message else ""
            recency = cand.metadata.get("recency_days", 0.0)

            if recency <= 1.0 and sender:
                if sender in seen_senders_24h:
                    logger.debug("Gate 2 suppressed duplicate candidate %s from sender %s within 24h", cand.message_id, sender)
                    continue
                seen_senders_24h.add(sender)
            suppressed.append(cand)

        return suppressed

    def _gate3_quality_thresholding(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Gate 3: Discard items with final_score < 0.35 unless exact sender/business match."""
        thresholded: List[RetrievalCandidate] = []
        target_sender = context.sender_id or (context.sender.user_id if context.sender else "")
        target_business = context.business.business_id if context.business else ""

        for cand in candidates:
            msg = cand.historical_message
            is_exact_match = False
            if msg:
                if target_sender and msg.sender_id == target_sender:
                    is_exact_match = True
                if target_business and msg.business_id == target_business:
                    is_exact_match = True

            if cand.final_score >= 0.35 or is_exact_match:
                thresholded.append(cand)
            else:
                logger.debug("Gate 3 dropped low-quality candidate %s (score=%.2f)", cand.message_id, cand.final_score)

        return thresholded

    def _gate4_conflict_resolution(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Gate 4: Resolve conflicting positive (replies) and negative (dismissals) evidence."""
        has_replies = any(c.behaviour_score > 0 for c in candidates)
        has_dismissals = any(c.behaviour_score < 0 for c in candidates)

        has_conflict = has_replies and has_dismissals
        for cand in candidates:
            cand.metadata["has_conflicting_evidence"] = has_conflict

        return candidates

    def _gate5_cold_start_handler(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Gate 5: Handle cold-start users or unknown business entities."""
        user_history_count = 0
        if context.history:
            user_history_count = getattr(context.history, "historical_message_count", getattr(context.history, "total_historical_messages", 0))

        if user_history_count < 3 and not candidates:
            logger.info("Gate 5 triggered cold-start fallback for user %s", context.user_id)
            for cand in candidates:
                cand.metadata["is_cold_start_fallback"] = True

        return candidates
