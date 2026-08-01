"""Unit tests for domain model entity calculations and invariants."""

from router.domain.entities.user import User
from router.domain.value_objects.message_id import InvalidMessageIdError, MessageId


def test_user_entity_rates(sample_user: User) -> None:
    """Verify User entity interaction rates calculation."""
    assert sample_user.total_interactions_30d == 75
    assert round(sample_user.open_rate, 2) == 0.67
    assert round(sample_user.reply_rate, 2) == 0.27


def test_message_id_validation() -> None:
    """Verify MessageId value object validation logic."""
    msg_id = MessageId("msg_123")
    assert str(msg_id) == "msg_123"

    try:
        MessageId("")
    except Exception as exc:
        assert isinstance(exc, InvalidMessageIdError)
