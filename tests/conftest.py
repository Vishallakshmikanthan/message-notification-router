"""Pytest fixtures for unit and integration testing."""

from datetime import UTC, datetime

import pytest

from router.domain.entities.message import Message
from router.domain.entities.user import User


@pytest.fixture
def dataset_dir() -> str:
    """Fixture returning dataset directory path."""
    return "./hackerrank-orchestrate-august26/dataset"


@pytest.fixture
def sample_user() -> User:
    """Fixture returning sample User domain entity."""
    return User(
        user_id="u_001",
        name="Alice Smith",
        do_not_disturb_window="22:00-07:00",
        messages_opened_30d=50,
        messages_replied_30d=20,
        notifications_dismissed_30d=5,
    )


@pytest.fixture
def sample_message() -> Message:
    """Fixture returning sample Message domain entity."""
    return Message(
        message_id="msg_001",
        user_id="u_001",
        conversation_type="personal",
        sender_user_id="u_002",
        message_text="Hey! Are we still meeting for lunch today?",
        created_at=datetime.now(UTC),
    )
