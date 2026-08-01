"""Unit tests for EvidenceValidator component."""

from datetime import datetime, timezone

from router.application.retrieval.evidence_validator import EvidenceValidator
from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import RetrievalCandidate
from router.domain.entities.history import HistoricalMessage


def test_validator_false_positive_filter() -> None:
    """Test Gate 1 entity contradiction false positive filtering."""
    validator = EvidenceValidator()

    context = MessageContext(
        message_id="q_100",
        user_id="u_01",
        message_text="Your verification code is 482910",
    )

    msg_contradiction = HistoricalMessage(
        message_id="m_bad",
        user_id="u_01",
        sender_id="sender_bad",
        conversation_type="personal",
        message_text="Your OTP for banking is 998811",
        created_at=datetime.now(timezone.utc),
    )

    cand = RetrievalCandidate(
        message_id="m_bad",
        historical_message=msg_contradiction,
        dense_score=0.85,
        bm25_score=0.0,
        final_score=0.80,
    )

    validated = validator.validate_candidates([cand], context)
    assert len(validated) == 0


def test_validator_pass_matching_entity() -> None:
    """Test valid candidate passing all 5 validation gates."""
    validator = EvidenceValidator()

    context = MessageContext(
        message_id="q_100",
        user_id="u_01",
        message_text="Your verification code is 482910",
        sender_id="auth_service",
    )

    msg_valid = HistoricalMessage(
        message_id="m_good",
        user_id="u_01",
        sender_id="auth_service",
        conversation_type="personal",
        message_text="Your verification code is 482910",
        created_at=datetime.now(timezone.utc),
    )

    cand = RetrievalCandidate(
        message_id="m_good",
        historical_message=msg_valid,
        dense_score=0.95,
        bm25_score=10.0,
        final_score=0.92,
    )

    validated = validator.validate_candidates([cand], context)
    assert len(validated) == 1
    assert validated[0].message_id == "m_good"
