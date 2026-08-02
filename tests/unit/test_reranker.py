"""Unit tests for Reranker component."""

from datetime import UTC, datetime

from router.application.retrieval.reranker import Reranker
from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import RetrievalCandidate
from router.domain.entities.history import HistoricalMessage


def test_reranker_scoring_and_floor() -> None:
    """Test Multi-Factor scoring and pre-score floor filtering."""
    reranker = Reranker(score_floor=0.30)
    context = MessageContext(
        message_id="q_01",
        user_id="u_01",
        sender_id="sender_1",
    )

    msg1 = HistoricalMessage(
        message_id="m1",
        user_id="u_01",
        sender_id="sender_1",
        conversation_type="personal",
        message_text="Your OTP verification code is 1234",
        created_at=datetime.now(UTC),
    )

    msg2 = HistoricalMessage(
        message_id="m2",
        user_id="u_01",
        sender_id="sender_99",
        conversation_type="personal",
        message_text="Random unrelated text",
        created_at=datetime.now(UTC),
    )

    cands = [
        RetrievalCandidate(message_id="m1", historical_message=msg1, dense_score=0.90),
        RetrievalCandidate(message_id="m2", historical_message=msg2, dense_score=0.05),
    ]

    reranked = reranker.rerank(cands, context)

    assert len(reranked) >= 1
    assert reranked[0].message_id == "m1"
    assert reranked[0].final_score >= 0.30


def test_exact_duplicate_hash_suppression() -> None:
    """Test exact text duplicate suppression."""
    reranker = Reranker()
    context = MessageContext(message_id="q_01", user_id="u_01")

    msg = HistoricalMessage(
        message_id="m1",
        user_id="u_01",
        sender_id="sender_1",
        conversation_type="personal",
        message_text="Identical broadcast message text",
        created_at=datetime.now(UTC),
    )

    cands = [
        RetrievalCandidate(message_id="m1", historical_message=msg, dense_score=0.85),
        RetrievalCandidate(message_id="m2", historical_message=msg, dense_score=0.80),
    ]

    reranked = reranker.rerank(cands, context)
    assert len(reranked) == 1
    assert reranked[0].message_id == "m1"
