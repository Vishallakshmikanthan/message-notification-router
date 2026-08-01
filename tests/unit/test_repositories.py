"""Unit tests for repository implementations."""

from router.domain.entities.message import Message
from router.domain.entities.user import User
from router.infrastructure.repositories.message_repository import MessageRepository
from router.infrastructure.repositories.user_repository import UserRepository


def test_user_repository_crud(sample_user: User) -> None:
    """Verify UserRepository add, get, count, exists ops."""
    repo = UserRepository()
    assert repo.count() == 0

    repo.add(sample_user.user_id, sample_user)
    assert repo.count() == 1
    assert repo.exists(sample_user.user_id) is True
    assert repo.get_by_id(sample_user.user_id) == sample_user


def test_message_repository_secondary_index(sample_message: Message) -> None:
    """Verify MessageRepository secondary user index functionality."""
    repo = MessageRepository()
    repo.add(sample_message.message_id, sample_message)

    user_msgs = repo.get_by_user_id(sample_message.user_id)
    assert len(user_msgs) == 1
    assert user_msgs[0].message_id == sample_message.message_id
