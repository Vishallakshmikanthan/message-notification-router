"""Unit tests for MessageContextFactory."""


from router.application.context.builder_pipeline import UnvalidatedContextBag
from router.application.context.context_factory import MessageContextFactory
from router.domain.entities.context import ContextQualityMetrics, MessageContext
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.entities.sub_contexts import (
    DEFAULT_BEHAVIOUR_CONTEXT,
    DEFAULT_BUSINESS_CONTEXT,
    DEFAULT_CONVERSATION_CONTEXT,
    DEFAULT_GROUP_CONTEXT,
    DEFAULT_HISTORY_CONTEXT,
    DEFAULT_MEDIA_CONTEXT,
    DEFAULT_NOTIFICATION_CONTEXT,
    DEFAULT_RELATIONSHIP_CONTEXT,
    DEFAULT_USER_CONTEXT,
)


def test_context_factory_creation():
    """Test MessageContextFactory constructing master MessageContext object."""
    factory = MessageContextFactory()

    payload = RawMessagePayload(
        message_id="msg_test_100",
        sender_phone="+15550100",
        receiver_phone="+15550200",
        content="Check this link https://example.com and call +15550300",
        timestamp=1700000000000,
        is_forwarded=True,
        forward_count=6,
    )

    bag = UnvalidatedContextBag(
        payload=payload,
        sender=DEFAULT_USER_CONTEXT,
        receiver=DEFAULT_USER_CONTEXT,
        group=DEFAULT_GROUP_CONTEXT,
        business=DEFAULT_BUSINESS_CONTEXT,
        media=DEFAULT_MEDIA_CONTEXT,
        history=DEFAULT_HISTORY_CONTEXT,
        notification_behaviour=DEFAULT_NOTIFICATION_CONTEXT,
        relationship=DEFAULT_RELATIONSHIP_CONTEXT,
        conversation=DEFAULT_CONVERSATION_CONTEXT,
        behaviour_stats=DEFAULT_BEHAVIOUR_CONTEXT,
    )

    metrics = ContextQualityMetrics(completeness_score=0.95)

    ctx = factory.create(bag, metrics, assembly_latency_ms=1.5)

    assert isinstance(ctx, MessageContext)
    assert ctx.core_message.message_id == "msg_test_100"
    assert ctx.core_message.contains_links is True
    assert ctx.core_message.contains_phone_numbers is True
    assert ctx.core_message.is_frequently_forwarded is True
    assert ctx.context_metadata.completeness_score == 0.95
    assert ctx.context_metadata.assembly_latency_ms == 1.5
    assert ctx.quality_metrics == metrics
