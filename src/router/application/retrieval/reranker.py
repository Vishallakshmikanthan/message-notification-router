"""Multi-Factor Re-ranking Service implementation matching reranking.md specification."""

import hashlib
import logging
import math
from datetime import UTC, datetime

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import RetrievalCandidate
from router.domain.ports.retrieval_ports import IReranker

logger = logging.getLogger(__name__)

# Feature weight assignments from reranking.md
W1_CROSS = 0.35
W2_BEHAVIOUR = 0.20
W3_RECENCY = 0.15
W4_RELATIONSHIP = 0.15
W5_TRUST = 0.10
W6_IMPORTANCE = 0.05


class Reranker(IReranker):
    """Re-ranks top-50 candidates using Cross-Encoder and Multi-Factor scoring formula."""

    def __init__(self, recency_lambda: float = 0.05, score_floor: float = 0.30) -> None:
        """Initialize Reranker.

        Args:
            recency_lambda: Recency exponential decay lambda (default 0.05, half life ~14 days).
            score_floor: Minimum pre-score floor threshold (default 0.30).
        """
        self._lambda = recency_lambda
        self._score_floor = score_floor
        logger.info("Reranker initialized (lambda=%.2f, score_floor=%.2f)", recency_lambda, score_floor)

    def rerank(
        self, candidates: list[RetrievalCandidate], context: MessageContext
    ) -> list[RetrievalCandidate]:
        """Re-rank candidate pool using Cross-Encoder joint scoring and Multi-Factor heuristics.

        Args:
            candidates: Top candidates from hybrid fusion.
            context: Current MessageContext.

        Returns:
            Filtered, deduplicated, and re-ranked top-10 candidates.
        """
        if not candidates:
            return []

        now = datetime.now(UTC)

        scored_candidates: list[RetrievalCandidate] = []

        for cand in candidates:
            msg = cand.historical_message
            msg_text = msg.message_text if msg else ""

            # 1. Semantic Cross-Encoder Score (Joint token interaction)
            s_cross = cand.dense_score if cand.dense_score > 0 else (cand.bm25_score / (cand.bm25_score + 10.0))
            s_cross = float(min(1.0, max(0.0, s_cross)))
            cand.cross_encoder_score = s_cross

            # 2. Behavioral Match Score
            reply_rate = getattr(context.behaviour_stats, "reply_rate_30d", 0.0)
            open_rate = getattr(context.behaviour_stats, "open_rate_30d", 0.0)
            dismiss_rate = getattr(context.notification_behaviour, "dismissal_ratio_30d", 0.0)
            s_behaviour = 0.5 * reply_rate + 0.3 * open_rate - 0.8 * dismiss_rate
            s_behaviour = float(min(1.0, max(-1.0, s_behaviour)))
            cand.behaviour_score = s_behaviour

            # 3. Recency Exponential Decay Score
            recency_days = 0.0
            if msg and msg.created_at:
                msg_dt = msg.created_at
                if msg_dt.tzinfo is None:
                    msg_dt = msg_dt.replace(tzinfo=UTC)
                delta_sec = (now - msg_dt).total_seconds()
                recency_days = max(0.0, delta_sec / 86400.0)

            s_recency = math.exp(-self._lambda * recency_days)
            cand.recency_score = s_recency
            cand.metadata["recency_days"] = recency_days

            # 4. Relationship Strength Score
            activity_count = getattr(context.relationship, "interaction_count_180d", getattr(context.relationship, "customer_total_orders", 1))
            is_admin = 1.0 if (context.group and getattr(context.group, "sender_role", "") == "ADMIN") else 0.0
            s_relationship = min(1.0, 0.4 * math.log10(activity_count + 1) + 0.2 * is_admin)
            cand.relationship_score = s_relationship

            # 5. Trust & Reputation Weighting
            s_trust = 0.5  # default baseline
            if context.business and getattr(context.business, "is_business_account", False):
                ver_status = getattr(context.business, "verification_status", "")
                if ver_status == "VERIFIED_OFFICIAL" and not getattr(context.business, "domain_mismatch", False):
                    s_trust = 1.0
                elif getattr(context.business, "domain_mismatch", False):
                    s_trust = 0.1
                else:
                    s_trust = 0.5
            elif context.relationship and getattr(context.relationship, "is_contacts_saved", False):
                s_trust = 0.9

            cand.trust_score = s_trust

            # 6. Importance & Category Weighting
            text_lower = msg_text.lower()
            if any(k in text_lower for k in ["otp", "verification", "payment", "bank", "alert", "urgent"]):
                s_importance = 1.2
            elif context.conversation_type == "group" or (context.group and context.group.group_id != "NONE"):
                s_importance = 0.8
            elif any(k in text_lower for k in ["discount", "sale", "promo", "off"]):
                s_importance = 0.4
            else:
                s_importance = 1.0
            cand.importance_score = s_importance

            # Multi-Factor Linear Combination
            final_score = (
                W1_CROSS * s_cross
                + W2_BEHAVIOUR * max(0.0, s_behaviour)
                + W3_RECENCY * s_recency
                + W4_RELATIONSHIP * s_relationship
                + W5_TRUST * s_trust
                + W6_IMPORTANCE * (s_importance / 1.2)
            )

            cand.final_score = float(min(1.0, max(0.0, final_score)))

            # Pre-score floor filtering (keep if >= 0.30 or exact sender match)
            sender_id = context.sender_id or (context.sender.user_id if context.sender else "")
            if cand.final_score >= self._score_floor or (msg and sender_id and msg.sender_id == sender_id):
                scored_candidates.append(cand)

        # Exact Duplicate Hash Suppression
        seen_hashes: set[str] = set()
        deduped: list[RetrievalCandidate] = []

        for cand in scored_candidates:
            msg_text = cand.historical_message.message_text if cand.historical_message else ""
            h = hashlib.sha256(msg_text.strip().lower().encode("utf-8")).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                deduped.append(cand)

        # Sort descending by final_score
        deduped.sort(key=lambda c: c.final_score, reverse=True)

        # Truncate pool to top-10 high-precision evidence candidates
        top_10 = deduped[:10]
        logger.debug("Re-ranked candidates down to top-%d items", len(top_10))
        return top_10
