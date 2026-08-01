"""Unit tests for HybridRetriever (Reciprocal Rank Fusion)."""

from router.application.retrieval.hybrid_retriever import HybridRetriever
from router.domain.entities.evidence import RetrievalCandidate, StructuredQuery


def test_hybrid_rrf_fusion() -> None:
    """Test RRF fusion logic and candidate merging."""
    hr = HybridRetriever(k=60)

    bm25_cands = [
        RetrievalCandidate(message_id="msg_A", bm25_score=15.0),
        RetrievalCandidate(message_id="msg_B", bm25_score=10.0),
    ]

    dense_cands = [
        RetrievalCandidate(message_id="msg_B", dense_score=0.95),
        RetrievalCandidate(message_id="msg_C", dense_score=0.80),
    ]

    query = StructuredQuery(
        user_id="u1",
        query_text="Sample query text",
        has_numeric_sequence=False,
    )

    fused = hr.fuse_results(bm25_cands, dense_cands, query)

    assert len(fused) == 3
    # msg_B is rank 2 in BM25 (w_bm25/(60+2)) and rank 1 in Dense (w_dense/(60+1))
    assert fused[0].message_id == "msg_B"
    assert fused[0].rrf_score > 0.0


def test_dynamic_modality_weights() -> None:
    """Test numeric query boosts BM25 weight to 0.70."""
    hr = HybridRetriever()

    q_numeric = StructuredQuery(
        user_id="u1",
        query_text="OTP 4819",
        has_numeric_sequence=True,
    )

    weights = hr.compute_modality_weights(q_numeric)
    assert weights["bm25"] == 0.70
    assert weights["dense"] == 0.30
