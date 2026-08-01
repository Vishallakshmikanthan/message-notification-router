"""Pytest fixtures for unit and integration testing."""

from datetime import datetime, timezone

import pytest

from router.domain.entities.message import Message
from router.domain.entities.user import User


@pytest.fixture
def sample_user() -> User:
    """Fixture returning sample User domain entity."""
    return User(
        user_id="u_001",
        user_name="Alice Smith",
        do_not_disturb_window="22:00-07:00",
        open_count_30d=50,
        reply_count_30d=20,
        dismiss_count_30d=5,
    )


@pytest.fixture
def sample_message() -> Message:
    """Fixture returning sample Message domain entity."""
    return Message(
        message_id="msg_001",
        user_id="u_001",
        conversation_type="personal",
        sender_id="u_002",
        message_text="Hey! Are we still meeting for lunch today?",
        created_at=datetime.now(timezone.utc),
    )
