"""Unit tests for ContextValidationService and ContextQualityEngine."""

import pytest

from router.application.context.builder_pipeline import UnvalidatedContextBag
from router.application.context.context_quality_engine import ContextQualityEngine
from router.application.context.context_validation_service import ContextValidationService
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
    MediaContext,
)
from router.domain.exceptions import InvalidPayloadException


def test_validator_raises_on_empty_message_id():
    """Test ContextValidationService raising InvalidPayloadException when message_id is empty."""
    validator = ContextValidationService()
    payload = RawMessagePayload(message_id="", sender_phone="+1", receiver_phone="+2")

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

    with pytest.raises(InvalidPayloadException):
        validator.validate(bag)


def test_validator_clamping_boundary_values():
    """Test boundary clamping filter in ContextValidationService."""
    validator = ContextValidationService()
    payload = RawMessagePayload(message_id="msg_001", sender_phone="+1", receiver_phone="+2")

    out_of_bounds_media = MediaContext(
        media_id="m1",
        media_type="IMAGE",
        sha256_hash="hash",
        has_media=True,
        image_risk_score=1.8,  # Needs clamping to 1.0
        voice_urgency_score=-0.5,  # Needs clamping to 0.0
    )

    bag = UnvalidatedContextBag(
        payload=payload,
        sender=DEFAULT_USER_CONTEXT,
        receiver=DEFAULT_USER_CONTEXT,
        group=DEFAULT_GROUP_CONTEXT,
        business=DEFAULT_BUSINESS_CONTEXT,
        media=out_of_bounds_media,
        history=DEFAULT_HISTORY_CONTEXT,
        notification_behaviour=DEFAULT_NOTIFICATION_CONTEXT,
        relationship=DEFAULT_RELATIONSHIP_CONTEXT,
        conversation=DEFAULT_CONVERSATION_CONTEXT,
        behaviour_stats=DEFAULT_BEHAVIOUR_CONTEXT,
    )

    val_bag, metrics = validator.validate(bag)
    assert val_bag.media.image_risk_score == 1.0
    assert val_bag.media.voice_urgency_score == 0.0
    assert 0.0 <= metrics.completeness_score <= 1.0


def test_quality_engine_score_calculation():
    """Test ContextQualityEngine calculating Q-score correctly."""
    engine = ContextQualityEngine()
    payload = RawMessagePayload(message_id="msg_001", sender_phone="+1", receiver_phone="+2", content="Hello")

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

    metrics = engine.compute_quality_score(bag)
    assert 0.0 <= metrics.completeness_score <= 1.0
    assert "user" in metrics.sub_context_scores
    assert "core_message" in metrics.sub_context_scores
