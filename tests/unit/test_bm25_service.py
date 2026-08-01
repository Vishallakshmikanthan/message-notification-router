"""Unit tests for BM25Service component."""

from datetime import datetime, timezone

from router.application.retrieval.bm25_service import BM25Service
from router.domain.entities.evidence import StructuredQuery
from router.domain.entities.history import HistoricalMessage


def test_bm25_indexing_and_search() -> None:
    """Test indexing corpus and searching with exact entity boost."""
    bm25 = BM25Service(k1=1.2, b=0.75)

    msg1 = HistoricalMessage(
        message_id="msg_001",
        user_id="user_123",
        sender_id="sender_A",
        conversation_type="personal",
        message_text="Your OTP for login is 482910. Do not share.",
        created_at=datetime.now(timezone.utc),
    )
    msg2 = HistoricalMessage(
        message_id="msg_002",
        user_id="user_123",
        sender_id="sender_B",
        conversation_type="personal",
        message_text="Hey, want to grab coffee today?",
        created_at=datetime.now(timezone.utc),
    )

    bm25.index_messages([msg1, msg2])

    query = StructuredQuery(
        user_id="user_123",
        query_text="What is my OTP code 482910?",
        sparse_terms=["otp", "482910"],
        has_numeric_sequence=True,
    )

    results = bm25.search(query, top_k=10)

    assert len(results) >= 1
    assert results[0].message_id == "msg_001"
    assert results[0].bm25_score > 0.0


def test_bm25_stopword_preservation() -> None:
    """Test that negation and urgency stopwords are preserved."""
    bm25 = BM25Service()
    tokens = bm25.tokenize("Urgent! Do not dismiss now!")

    assert "urgent" in tokens
    assert "not" in tokens
    assert "now" in tokens
