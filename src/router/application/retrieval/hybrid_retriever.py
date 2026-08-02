"""Hybrid Search Fusion Service using Reciprocal Rank Fusion (RRF) as specified in hybrid_search.md."""

import logging

from router.domain.entities.evidence import RetrievalCandidate, StructuredQuery
from router.domain.ports.retrieval_ports import IHybridRetriever

logger = logging.getLogger(__name__)


class HybridRetriever(IHybridRetriever):
    """Fuses sparse BM25 and dense embedding candidate sets using Reciprocal Rank Fusion."""

    def __init__(self, k: int = 60) -> None:
        """Initialize HybridRetriever.

        Args:
            k: RRF smoothing constant (default 60).
        """
        self.k = k
        logger.info("HybridRetriever initialized with RRF k=%d", k)

    def compute_modality_weights(self, query: StructuredQuery) -> dict[str, float]:
        """Compute dynamic modality weights (w_BM25 vs w_Dense) based on query attributes.

        Rules from hybrid_search.md:
        - Numeric sequence / order ID / OTP -> w_BM25=0.70, w_Dense=0.30
        - URL domain / domain mismatch -> w_BM25=0.65, w_Dense=0.35
        - Conversational / text > 15 words -> w_BM25=0.35, w_Dense=0.65
        - Default balanced -> w_BM25=0.50, w_Dense=0.50
        """
        words = query.query_text.split() if query.query_text else []

        if query.has_numeric_sequence:
            w_bm25, w_dense = 0.70, 0.30
        elif query.has_url_domain or query.domain_mismatch:
            w_bm25, w_dense = 0.65, 0.35
        elif len(words) > 15:
            w_bm25, w_dense = 0.35, 0.65
        else:
            w_bm25, w_dense = 0.50, 0.50

        return {"bm25": w_bm25, "dense": w_dense}

    def fuse_results(
        self,
        bm25_candidates: list[RetrievalCandidate],
        dense_candidates: list[RetrievalCandidate],
        query: StructuredQuery,
    ) -> list[RetrievalCandidate]:
        """Fuse sparse and dense candidates using RRF and dynamic weighting.

        Args:
            bm25_candidates: Top BM25 candidates (sorted descending).
            dense_candidates: Top dense candidates (sorted descending).
            query: StructuredQuery used for retrieval.

        Returns:
            Unified candidate pool sorted descending by rrf_score (top-50 truncated).
        """
        weights = self.compute_modality_weights(query)
        w_bm25 = weights["bm25"]
        w_dense = weights["dense"]

        merged: dict[str, RetrievalCandidate] = {}

        # Process BM25 ranks
        for rank_idx, cand in enumerate(bm25_candidates, start=1):
            msg_id = cand.message_id
            if msg_id not in merged:
                merged[msg_id] = cand
            merged[msg_id].bm25_rank = rank_idx
            merged[msg_id].bm25_score = cand.bm25_score

        # Process Dense ranks
        for rank_idx, cand in enumerate(dense_candidates, start=1):
            msg_id = cand.message_id
            if msg_id not in merged:
                merged[msg_id] = cand
            merged[msg_id].dense_rank = rank_idx
            merged[msg_id].dense_score = cand.dense_score

        # Calculate RRF score for each merged candidate
        fused_list: list[RetrievalCandidate] = []
        for msg_id, cand in merged.items():
            rrf_score = 0.0
            if cand.bm25_rank is not None:
                rrf_score += w_bm25 / (self.k + cand.bm25_rank)
            if cand.dense_rank is not None:
                rrf_score += w_dense / (self.k + cand.dense_rank)

            cand.rrf_score = rrf_score
            fused_list.append(cand)

        # Sort descending by RRF score
        fused_list.sort(key=lambda c: c.rrf_score, reverse=True)

        # Truncate to top-50 for re-ranking
        top_50 = fused_list[:50]
        logger.debug("Fused %d candidates down to top-%d pool", len(fused_list), len(top_50))
        return top_50
