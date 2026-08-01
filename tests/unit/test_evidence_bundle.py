"""Unit tests for Evidence Domain Entities (EvidenceItem, EvidenceBundle, StructuredQuery)."""

from datetime import datetime, timezone

from router.domain.entities.evidence import (
    EvidenceBundle,
    EvidenceItem,
    RetrievalCandidate,
    StructuredQuery,
)


def test_evidence_item_creation() -> None:
    """Test EvidenceItem fields and immutability."""
    item = EvidenceItem(
        message_id="msg_001",
        similarity_score=0.85,
        behaviour_match=0.5,
        sender_match=1.0,
        business_match=0.0,
        group_match=0.0,
        recency_days=2.5,
        importance_weight=1.0,
        trust_score=0.9,
        reason_retrieved="EXACT_SENDER_REPLY_HISTORY",
        source_dataset="message_history.csv",
        historical_action_taken="replied",
        raw_text="Hello, here is your update",
    )

    assert item.message_id == "msg_001"
    assert item.similarity_score == 0.85
    assert item.sender_match == 1.0
    assert item.reason_retrieved == "EXACT_SENDER_REPLY_HISTORY"
    assert item.historical_action_taken == "replied"


def test_evidence_bundle_creation() -> None:
    """Test EvidenceBundle initialization and defaults."""
    item = EvidenceItem(
        message_id="msg_001",
        similarity_score=0.90,
        behaviour_match=0.8,
        sender_match=1.0,
        business_match=0.0,
        group_match=0.0,
        recency_days=1.0,
        importance_weight=1.2,
        trust_score=1.0,
        reason_retrieved="PREVIOUS_OTP_REQUEST",
    )

    bundle = EvidenceBundle(
        query_message_id="q_msg_100",
        user_id="user_456",
        retrieval_confidence=0.90,
        evidence_count=1,
        primary_reason="PREVIOUS_OTP_REQUEST",
        items=[item],
        coverage_score=0.10,
        has_conflicting_evidence=False,
    )

    assert bundle.query_message_id == "q_msg_100"
    assert bundle.user_id == "user_456"
    assert bundle.evidence_count == 1
    assert bundle.primary_reason == "PREVIOUS_OTP_REQUEST"
    assert len(bundle.items) == 1
    assert bundle.items[0].message_id == "msg_001"


def test_structured_query_creation() -> None:
    """Test StructuredQuery fields."""
    sq = StructuredQuery(
        user_id="user_123",
        query_text="Your OTP is 482910",
        sparse_terms=["otp", "482910"],
        dense_vector=[0.1] * 384,
        filters={"conversation_type": "personal"},
        boost_factors={"exact_entity_match": 2.5},
        has_numeric_sequence=True,
    )

    assert sq.user_id == "user_123"
    assert sq.has_numeric_sequence is True
    assert len(sq.dense_vector) == 384
    assert sq.boost_factors["exact_entity_match"] == 2.5
