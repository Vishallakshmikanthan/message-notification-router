"""Evidence Assembler implementation matching evidence_models.md specification."""

import logging
from datetime import UTC, datetime

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import EvidenceBundle, EvidenceItem, RetrievalCandidate
from router.domain.ports.retrieval_ports import IEvidenceAssembler

logger = logging.getLogger(__name__)


class EvidenceAssembler(IEvidenceAssembler):
    """Assembles validated candidate objects into an immutable EvidenceBundle."""

    def __init__(self) -> None:
        """Initialize EvidenceAssembler."""
        logger.info("EvidenceAssembler initialized")

    def assemble_bundle(
        self, validated_candidates: list[RetrievalCandidate], context: MessageContext
    ) -> EvidenceBundle:
        """Construct immutable EvidenceBundle from validated candidates.

        Args:
            validated_candidates: Validated candidate items.
            context: Current MessageContext.

        Returns:
            EvidenceBundle container.
        """
        query_msg_id = context.message_id or context.core_message.message_id or "UNKNOWN_MSG"
        user_id = context.user_id or context.receiver.user_id or "UNKNOWN_USER"
        target_sender = context.sender_id or (context.sender.user_id if context.sender else "")
        target_business = context.business.business_id if context.business else ""
        target_group = context.group.group_id if context.group else ""

        items: list[EvidenceItem] = []
        has_conflicting = False

        for cand in validated_candidates:
            msg = cand.historical_message
            msg_id = cand.message_id
            msg_text = msg.message_text if msg else ""
            created_at_iso = msg.created_at.isoformat() if msg and msg.created_at else ""

            # Calculate match degrees
            sender_match = 1.0 if (msg and target_sender and msg.sender_id == target_sender) else 0.0
            business_match = 1.0 if (msg and target_business and msg.business_id == target_business) else 0.0
            group_match = 1.0 if (msg and target_group and msg.group_id == target_group) else 0.0

            # Determine taxonomy reason and action
            reason = self._determine_reason(cand, sender_match, business_match, group_match, msg_text)
            action = self._determine_action(cand)

            if cand.metadata.get("has_conflicting_evidence", False):
                has_conflicting = True

            item = EvidenceItem(
                message_id=msg_id,
                similarity_score=cand.final_score,
                behaviour_match=cand.behaviour_score,
                sender_match=sender_match,
                business_match=business_match,
                group_match=group_match,
                recency_days=cand.metadata.get("recency_days", 0.0),
                importance_weight=cand.importance_score,
                trust_score=cand.trust_score,
                reason_retrieved=reason,
                source_dataset="message_history.csv",
                historical_action_taken=action,
                raw_text=msg_text,
                created_at_iso=created_at_iso,
            )
            items.append(item)

        # Retrieval confidence calculation
        confidence = 0.0
        if items:
            confidence = float(sum(i.similarity_score for i in items) / len(items))

        # Primary reason
        primary_reason = items[0].reason_retrieved if items else "NO_HISTORICAL_EVIDENCE"

        # Coverage score (ratio of retrieved items to target capacity 10)
        coverage_score = float(min(1.0, len(items) / 10.0))

        bundle = EvidenceBundle(
            query_message_id=query_msg_id,
            user_id=user_id,
            timestamp=datetime.now(UTC).isoformat(),
            retrieval_confidence=confidence,
            evidence_count=len(items),
            primary_reason=primary_reason,
            items=items,
            coverage_score=coverage_score,
            has_conflicting_evidence=has_conflicting,
        )

        logger.info(
            "Assembled EvidenceBundle for msg %s (items=%d, confidence=%.2f, primary_reason=%s)",
            query_msg_id,
            len(items),
            confidence,
            primary_reason,
        )
        return bundle

    def _determine_reason(
        self,
        cand: RetrievalCandidate,
        sender_match: float,
        business_match: float,
        group_match: float,
        text: str,
    ) -> str:
        """Determine taxonomic retrieval reason for an evidence item."""
        text_lower = text.lower()
        if "otp" in text_lower or "verification" in text_lower:
            return "PREVIOUS_OTP_REQUEST"
        if "paid" in text_lower or "receipt" in text_lower or "transaction" in text_lower:
            return "PAST_TRANSACTION_RECEIPT"
        if cand.trust_score <= 0.1:
            return "REPEATED_SCAM_PATTERN"
        if sender_match == 1.0 and cand.behaviour_score > 0:
            return "EXACT_SENDER_REPLY_HISTORY"
        if sender_match == 1.0 and cand.behaviour_score < 0:
            return "EXACT_SENDER_DISMISSAL_HISTORY"
        if group_match == 1.0:
            return "GROUP_ACTIVITY_PRECEDENT"
        if "promo" in text_lower or "sale" in text_lower:
            return "SIMILAR_PROMOTIONAL_DISMISSAL"
        return "SIMILAR_HISTORICAL_MESSAGE"

    def _determine_action(self, cand: RetrievalCandidate) -> str:
        """Determine historical action taken on evidence item."""
        if cand.behaviour_score > 0.3:
            return "replied"
        if cand.behaviour_score < -0.3:
            return "dismissed"
        if cand.trust_score <= 0.1:
            return "reported"
        return "opened"
