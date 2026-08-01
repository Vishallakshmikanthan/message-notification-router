"""Unit tests for ContextAssembler (ContextAssemblyEngine)."""

from datetime import datetime, timezone
import pytest

from router.application.context.context_assembler import ContextAssembler
from router.domain.entities.context import MessageContext
from router.domain.entities.message import Message
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.exceptions import InvalidPayloadException
from router.infrastructure.cache.context_cache import ContextCache
from router.infrastructure.repositories.context_repository_registry import ContextRepositoryRegistry


def test_context_assembler_single_message():
    """Test assembling a single RawMessagePayload produces one MessageContext."""
    assembler = ContextAssembler()

    payload = RawMessagePayload(
        message_id="msg_full_001",
        sender_phone="+15551234567",
        receiver_phone="+15559876543",
        content="Meeting at 4pm today",
        timestamp=1700000000000,
    )

    ctx = assembler.assemble(payload)

    assert isinstance(ctx, MessageContext)
    assert ctx.core_message.message_id == "msg_full_001"
    assert ctx.sender.phone_number == "+15551234567"
    assert ctx.receiver.phone_number == "+15559876543"
    assert ctx.context_metadata.completeness_score > 0.0


def test_context_assembler_domain_message():
    """Test assembling a domain Message object."""
    assembler = ContextAssembler()

    msg = Message(
        message_id="msg_domain_002",
        user_id="+15559876543",
        sender_id="+15551234567",
        conversation_type="personal",
        message_text="Hello world!",
        created_at=datetime.now(timezone.utc),
    )

    ctx = assembler.assemble(msg)

    assert isinstance(ctx, MessageContext)
    assert ctx.core_message.message_id == "msg_domain_002"
    assert ctx.core_message.cleaned_text == "Hello world!"


def test_context_assembler_determinism():
    """Test determinism: assembling the same payload twice yields identical objects."""
    assembler = ContextAssembler()

    payload = RawMessagePayload(
        message_id="msg_det_003",
        sender_phone="+15551111111",
        receiver_phone="+15552222222",
        content="Deterministic content check",
        timestamp=1700000000000,
    )

    ctx1 = assembler.assemble(payload)
    ctx2 = assembler.assemble(payload)

    assert ctx1.core_message == ctx2.core_message
    assert ctx1.temporal_info == ctx2.temporal_info
    assert ctx1.sender == ctx2.sender
    assert ctx1.receiver == ctx2.receiver
    assert ctx1.group == ctx2.group
    assert ctx1.business == ctx2.business
    assert ctx1.media == ctx2.media


def test_context_assembler_batch():
    """Test assemble_batch processing multiple messages."""
    assembler = ContextAssembler()

    payloads = [
        RawMessagePayload(message_id="m1", sender_phone="+1", receiver_phone="+2", content="Msg 1"),
        RawMessagePayload(message_id="m2", sender_phone="+3", receiver_phone="+4", content="Msg 2"),
    ]

    contexts = assembler.assemble_batch(payloads)
    assert len(contexts) == 2
    assert contexts[0].core_message.message_id == "m1"
    assert contexts[1].core_message.message_id == "m2"


def test_context_assembler_corrupted_payload_raises():
    """Test assembling invalid payload without message_id raises InvalidPayloadException."""
    assembler = ContextAssembler()

    with pytest.raises(InvalidPayloadException):
        assembler.assemble({"message_id": "", "content": "No ID"})
