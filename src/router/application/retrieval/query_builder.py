"""QueryBuilder service implementation matching query_builder.md specification."""

import logging
import re
from typing import List, Optional

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import StructuredQuery
from router.domain.ports.retrieval_ports import IEmbeddingService, IQueryBuilder

logger = logging.getLogger(__name__)

# Taxonomy synonym mapping
TAXONOMY_SYNONYMS = {
    "otp": ["verification code", "2fa", "security pin", "auth code", "one time password"],
    "verification": ["otp", "2fa", "security code"],
    "discount": ["sale", "off", "cashback", "coupon", "offer", "promo"],
    "shipped": ["out for delivery", "arriving today", "dispatch", "order update", "tracking"],
    "payment": ["transaction", "receipt", "paid", "debited", "credited", "bank alert"],
}


class QueryBuilder(IQueryBuilder):
    """Builds and expands structured queries from incoming MessageContext."""

    def __init__(self, embedding_service: Optional[IEmbeddingService] = None) -> None:
        """Initialize QueryBuilder with optional EmbeddingService.

        Args:
            embedding_service: Service for generating dense query vector embeddings.
        """
        self._embedding_service = embedding_service
        logger.info("QueryBuilder initialized")

    def build_query(self, context: MessageContext) -> StructuredQuery:
        """Construct structured, high-precision search query from MessageContext.

        Args:
            context: Master MessageContext.

        Returns:
            StructuredQuery instance containing sparse terms, dense vector, filters, boost factors.
        """
        user_id = context.user_id or (context.receiver.user_id if context.receiver else "UNKNOWN_USER")
        raw_text = context.message_text or (context.core_message.cleaned_text if context.core_message else "") or ""

        # Multimodal Text Aggregation safely accessing properties
        ocr_text = context.media_ocr_text or (
            context.media.ocr_extracted_text if context.media else ""
        ) or ""
        vlm_caption = context.media_vlm_caption or (
            context.media.image_summary if context.media else ""
        ) or ""
        voice_transcript = context.voice_transcript or (
            context.media.voice_transcript if context.media else ""
        ) or ""

        composite_text_parts = [p for p in [raw_text, vlm_caption, ocr_text, voice_transcript] if p]
        composite_text = " ".join(composite_text_parts)

        # Token Extraction & Preprocessing
        base_tokens = self._extract_tokens(composite_text)

        # Detect Special Patterns
        has_numeric = bool(re.search(r"\b\d{4,10}\b", composite_text))
        has_url = "http" in composite_text.lower() or "www." in composite_text.lower() or ".com" in composite_text.lower()

        # Domain Mismatch Detection
        domain_mismatch = False
        sender_domain = ""
        official_domain = ""
        if context.business and getattr(context.business, "is_business_account", False):
            official_domain = getattr(context.business, "official_domain", "") or getattr(context.business, "support_email", "")
            sender_domain = getattr(context.business, "domain_used_by_sender", "")
            if sender_domain and official_domain and sender_domain.lower() != official_domain.lower():
                domain_mismatch = True

        # Taxonomy & Expansion Tokens
        expansion_tokens: List[str] = []
        for token in base_tokens:
            token_lower = token.lower()
            if token_lower in TAXONOMY_SYNONYMS:
                expansion_tokens.extend(TAXONOMY_SYNONYMS[token_lower])

        if domain_mismatch or getattr(context.business, "domain_mismatch", False):
            domain_mismatch = True
            expansion_tokens.extend(["domain_mismatch", "suspicious_url", "phishing_check"])

        # User Behavior Influences
        behaviour_flags: List[str] = []
        dismissal_rate = getattr(context.notification_behaviour, "dismissal_ratio_30d", 0.0)
        reply_rate = getattr(context.behaviour_stats, "reply_rate_30d", 0.0)

        if dismissal_rate > 0.70:
            behaviour_flags.append("high_dismissal_channel")
        if reply_rate > 0.50:
            behaviour_flags.append("high_reply_sender")
        if getattr(context, "is_quiet_hours", False):
            behaviour_flags.append("user_dnd_active")

        expansion_tokens.extend(behaviour_flags)

        # Unified Sparse Terms
        sparse_terms = list(dict.fromkeys(base_tokens + expansion_tokens))

        # Filters
        sender_id = context.sender_id or (context.sender.user_id if context.sender else None)
        group_id = context.group.group_id if context.group and context.group.group_id != "NONE" else None
        business_id = context.business.business_id if context.business and context.business.business_id != "NONE" else None

        filters = {
            "conversation_type": context.conversation_type or "personal",
            "group_id": group_id,
            "business_id": business_id,
            "sender_user_id": sender_id,
        }

        # Boost Factors
        boost_factors = {
            "exact_entity_match": 2.5 if (has_numeric or has_url) else 1.0,
            "sender_match": 3.0 if filters["sender_user_id"] else 1.0,
            "category_match": 1.5,
            "recency_bias": 1.2,
        }

        # Generate Dense Query Vector
        dense_vector: List[float] = []
        if self._embedding_service:
            dense_vector = self._embedding_service.generate_embedding(composite_text or raw_text)

        logger.debug(
            "Built StructuredQuery for user %s with %d sparse terms (has_numeric=%s, domain_mismatch=%s)",
            user_id,
            len(sparse_terms),
            has_numeric,
            domain_mismatch,
        )

        return StructuredQuery(
            user_id=user_id,
            query_text=raw_text,
            sparse_terms=sparse_terms,
            dense_vector=dense_vector,
            filters=filters,
            boost_factors=boost_factors,
            expansion_tokens=expansion_tokens,
            has_numeric_sequence=has_numeric,
            has_url_domain=has_url,
            domain_mismatch=domain_mismatch,
        )

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract clean tokens from text string."""
        if not text:
            return []
        cleaned = re.sub(r"[^\w\s\-\.\$]", " ", text.lower())
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
        return tokens
