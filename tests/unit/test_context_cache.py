"""Unit tests for ContextCache multi-level caching topology."""

from unittest.mock import MagicMock

from router.domain.entities.user import User
from router.infrastructure.cache.context_cache import ContextCache


def test_context_cache_l1_tier():
    """Test L1 Hot Entity Cache put and get operations."""
    cache = ContextCache(max_l1_entries=2)

    user = MagicMock(spec=User)
    user.user_id = "user_001"

    cache.put_user("user_001", user)
    assert cache.get_user("user_001") == user
    assert cache.get_user("user_999") is None


def test_context_cache_l2_tier():
    """Test L2 Relational Index Cache operations."""
    cache = ContextCache()
    member = MagicMock()

    cache.put_group_member("group_1", "user_1", member)
    assert cache.get_group_member("group_1", "user_1") == member
    assert cache.get_group_member("group_1", "user_2") is None


def test_context_cache_l3_tier():
    """Test L3 Multimodal Cache storage and clearance."""
    cache = ContextCache()
    artifact = {"ocr_text": "Sample Receipt"}

    cache.put_multimodal("hash_abc123", artifact)
    assert cache.get_multimodal("hash_abc123") == artifact

    cache.clear()
    assert cache.get_multimodal("hash_abc123") is None
