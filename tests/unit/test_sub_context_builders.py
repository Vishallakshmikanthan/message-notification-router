"""Unit tests for individual Sub-Context Builders."""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from router.application.context.sub_builders import (
    BehaviourContextBuilder,
    BusinessContextBuilder,
    ConversationContextBuilder,
    GroupContextBuilder,
    HistoryContextBuilder,
    MediaContextBuilder,
    NotificationContextBuilder,
    RelationshipContextBuilder,
    UserContextBuilder,
)
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.entities.sub_contexts import (
    DEFAULT_BUSINESS_CONTEXT,
    DEFAULT_GROUP_CONTEXT,
    DEFAULT_MEDIA_CONTEXT,
    DEFAULT_USER_CONTEXT,
    BusinessContext,
    GroupContext,
    HistoryContext,
    UserContext,
)
from router.infrastructure.cache.context_cache import ContextCache
from router.infrastructure.repositories.context_repository_registry import ContextRepositoryRegistry


def test_user_context_builder_fallback():
    """Test UserContextBuilder returning default or unregistered profile when user missing."""
    builder = UserContextBuilder()
    registry = ContextRepositoryRegistry()

    ctx = builder.build("UNKNOWN_USER", registry)
    assert ctx == DEFAULT_USER_CONTEXT

    ctx_unreg = builder.build("+15559990000", registry)
    assert ctx_unreg.is_registered_user is False
    assert ctx_unreg.phone_number == "+15559990000"


def test_group_context_builder_dm_fallback():
    """Test GroupContextBuilder returning default DM context when group_id is NONE."""
    builder = GroupContextBuilder()
    registry = ContextRepositoryRegistry()

    ctx = builder.build("NONE", "+15550001", registry)
    assert ctx == DEFAULT_GROUP_CONTEXT
    assert ctx.group_type == "DIRECT_CHAT"


def test_business_context_builder_fallback():
    """Test BusinessContextBuilder returning default non-business context when business_id is NONE."""
    builder = BusinessContextBuilder()
    registry = ContextRepositoryRegistry()

    ctx = builder.build("NONE", registry)
    assert ctx == DEFAULT_BUSINESS_CONTEXT
    assert ctx.is_business_account is False


def test_media_context_builder_text_only():
    """Test MediaContextBuilder returning default media context for text-only messages."""
    builder = MediaContextBuilder()
    registry = ContextRepositoryRegistry()
    payload = RawMessagePayload(
        message_id="msg_001",
        sender_phone="+1555001",
        receiver_phone="+1555002",
        media_hash="",
        media_type="TEXT",
    )

    ctx = builder.build(payload, registry)
    assert ctx == DEFAULT_MEDIA_CONTEXT
    assert ctx.has_media is False


def test_relationship_context_builder_p2p():
    """Test RelationshipContextBuilder synthesizing peer-to-peer relationship."""
    builder = RelationshipContextBuilder()
    registry = ContextRepositoryRegistry()

    user_ctx = UserContext(
        user_id="u1",
        display_name="User One",
        phone_number="+155501",
        user_type="INDIVIDUAL",
        registration_timestamp=0,
        account_age_days=10,
        preferred_language="en",
        timezone="UTC",
        is_verified=True,
    )
    history_ctx = HistoryContext(
        historical_message_count=10,
        last_interaction_timestamp=0,
        days_since_last_interaction=1.0,
    )

    rel = builder.build(user_ctx, DEFAULT_BUSINESS_CONTEXT, DEFAULT_GROUP_CONTEXT, history_ctx, registry)
    assert rel.relationship_type == "PEER_TO_PEER"
    assert rel.is_contacts_saved is True


def test_conversation_context_builder():
    """Test ConversationContextBuilder setting thread attributes."""
    builder = ConversationContextBuilder()
    payload = RawMessagePayload(
        message_id="msg_01",
        sender_phone="+155501",
        receiver_phone="+155502",
    )

    conv = builder.build(payload, DEFAULT_GROUP_CONTEXT)
    assert conv.is_group_chat is False
    assert conv.active_participant_count == 2
    assert "DM_" in conv.conversation_id
