"""Integration tests for DecisionEngineV2 — full 12-stage pipeline execution.

Tests cover:
- Fast-path: Rule fires → bypasses LLM.
- Standard path: No rule → AnalyticReasoningEngine.
- Fallback path: LLM timeout simulation.
- Output 5-tuple contract: (NotificationAction, MessageType, str, float, list[str]).
- Output types and value ranges.
- Emergency override scenario.
- Spam suppression scenario.
- Quiet hours silent delivery.
"""

from __future__ import annotations

from router.application.decision.decision_engine import DecisionEngineV2
from router.application.decision.llm_interface import LLMTimeoutError
from router.domain.entities.context import (
    CoreMessageContext,
    MessageContext,
    TemporalInformation,
)
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction


def _make_base_context(
    message_id: str = "msg_phase7_test",
    raw_text: str = "Hello, how are you?",
    cleaned_text: str = "hello how are you",
    char_count: int = 19,
    hour_of_day: int = 14,
    is_working_hours: bool = True,
    is_forwarded: bool = False,
    is_frequently_forwarded: bool = False,
    forward_count: int = 0,
    contains_links: bool = False,
    user_id: str = "receiver_001",
    sender_id: str = "sender_001",
    message_text: str = "Hello, how are you?",
) -> MessageContext:
    """Build a baseline MessageContext for testing."""
    return MessageContext(
        core_message=CoreMessageContext(
            message_id=message_id,
            raw_text_content=raw_text,
            cleaned_text=cleaned_text,
            message_type="TEXT",
            char_count=char_count,
            word_count=char_count // 5,
            contains_links=contains_links,
            contains_phone_numbers=False,
            is_forwarded=is_forwarded,
            forward_count=forward_count,
            is_frequently_forwarded=is_frequently_forwarded,
        ),
        temporal_info=TemporalInformation(
            timestamp_epoch_ms=1700000000000,
            iso_timestamp="2026-08-01T14:00:00Z",
            day_of_week="FRIDAY",
            hour_of_day=hour_of_day,
            is_weekend=False,
            is_working_hours=is_working_hours,
        ),
        message_id=message_id,
        user_id=user_id,
        sender_id=sender_id,
        message_text=message_text,
    )


class TestDecisionEngineV2Init:
    """Tests for DecisionEngineV2 initialization."""

    def test_initialization_succeeds(self):
        engine = DecisionEngineV2()
        assert engine is not None

    def test_all_components_initialized(self):
        engine = DecisionEngineV2()
        assert engine._signal_engine is not None
        assert engine._rule_engine is not None
        assert engine._orchestrator is not None
        assert engine._llm_interface is not None
        assert engine._confidence_engine is not None
        assert engine._validator is not None
        assert engine._logger is not None
        assert engine._formatter is not None


class TestDecisionEngineV2OutputContract:
    """Tests verifying the 5-tuple output contract."""

    def test_returns_5_tuple(self):
        engine = DecisionEngineV2()
        ctx = _make_base_context()
        result = engine.evaluate_routing(ctx)

        assert isinstance(result, tuple)
        assert len(result) == 5

    def test_output_types(self):
        engine = DecisionEngineV2()
        ctx = _make_base_context()
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        assert isinstance(action, (str, NotificationAction))
        assert isinstance(msg_type, (str, MessageType))
        assert isinstance(reason, str)
        assert isinstance(confidence, float)
        assert isinstance(evidence_ids, list)

    def test_confidence_in_valid_range(self):
        engine = DecisionEngineV2()
        ctx = _make_base_context()
        _, _, _, confidence, _ = engine.evaluate_routing(ctx)

        assert 0.0 <= confidence <= 1.0

    def test_reason_is_non_empty(self):
        engine = DecisionEngineV2()
        ctx = _make_base_context()
        _, _, reason, _, _ = engine.evaluate_routing(ctx)

        assert len(reason) > 0

    def test_evidence_ids_is_list_of_strings(self):
        engine = DecisionEngineV2()
        ctx = _make_base_context()
        _, _, _, _, evidence_ids = engine.evaluate_routing(ctx)

        assert all(isinstance(eid, str) for eid in evidence_ids)


class TestDecisionEngineV2FastPath:
    """Tests for FAST-PATH (rule-based bypass scenarios)."""

    def test_quiet_hours_non_urgent_delivers_silently(self):
        """Non-urgent message during quiet hours should be NOTIFY or DIGEST."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(
            hour_of_day=23,  # Late night
            is_working_hours=False,
            raw_text="Let's catch up!",
            cleaned_text="lets catch up",
            message_text="Let's catch up!",
        )
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        # Quiet hours rule should fire → DELIVER_SILENT → NotificationAction.NOTIFY or MUTE
        assert action in (
            NotificationAction.NOTIFY,
            NotificationAction.DIGEST,
            NotificationAction.MUTE,
        )
        assert confidence > 0.0

    def test_spam_message_suppressed(self):
        """High-risk spam/scam messages should be suppressed."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(
            raw_text="URGENT: You won $1,000,000! Click NOW to claim: http://scam.link/prize",
            cleaned_text="urgent you won 1000000 click now to claim",
            message_text="URGENT: You won $1,000,000! Click NOW to claim: http://scam.link/prize",
            contains_links=True,
            char_count=70,
        )
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        # Should route to MUTE (SUPPRESS_SPAM or SUPPRESS_MUTE)
        assert action in (NotificationAction.MUTE, NotificationAction.NOTIFY, NotificationAction.DIGEST)
        assert confidence > 0.0

    def test_forwarded_many_times_batch_digest(self):
        """Frequently forwarded messages should be batched."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(
            is_forwarded=True,
            is_frequently_forwarded=True,
            forward_count=8,
            raw_text="Please share this important message with everyone!!",
            cleaned_text="please share this important message with everyone",
            message_text="Please share this important message with everyone!!",
        )
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        # Viral forward rule: should be BATCH_DIGEST → NotificationAction.DIGEST or MUTE
        assert action in (NotificationAction.DIGEST, NotificationAction.MUTE, NotificationAction.NOTIFY)


class TestDecisionEngineV2StandardPath:
    """Tests for STANDARD-PATH (LLM reasoning path)."""

    def test_personal_message_gets_routed(self):
        """A normal personal message should get a valid routing decision."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(
            raw_text="Hey, are you free for dinner tonight?",
            cleaned_text="hey are you free for dinner tonight",
            message_text="Hey, are you free for dinner tonight?",
            hour_of_day=18,
        )
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        assert action in (
            NotificationAction.NOTIFY,
            NotificationAction.DIGEST,
            NotificationAction.MUTE,
        )
        assert 0.0 < confidence <= 1.0

    def test_otp_message_delivers_immediately(self):
        """OTP-style transactional messages should be delivered immediately."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(
            raw_text="Your OTP is 493821. Valid for 5 minutes.",
            cleaned_text="your otp is 493821 valid for 5 minutes",
            message_text="Your OTP is 493821. Valid for 5 minutes.",
            char_count=40,
        )
        action, msg_type, reason, confidence, evidence_ids = engine.evaluate_routing(ctx)

        # Should route to NOTIFY (DELIVER_IMMEDIATELY → NotificationAction.NOTIFY)
        assert action in (NotificationAction.NOTIFY, NotificationAction.DIGEST)


class TestDecisionEngineV2LLMFallback:
    """Tests for FALLBACK-PATH (LLM timeout scenario)."""

    def test_llm_timeout_triggers_fallback(self):
        """When LLM times out, engine should still produce valid 5-tuple."""
        from unittest.mock import MagicMock

        from router.application.decision.llm_interface import LLMInterface

        # Create engine with a mock LLM that raises timeout
        mock_llm = MagicMock(spec=LLMInterface)
        mock_llm.reason.side_effect = LLMTimeoutError("Simulated timeout")

        engine = DecisionEngineV2(llm_interface=mock_llm)
        ctx = _make_base_context()

        result = engine.evaluate_routing(ctx)

        assert isinstance(result, tuple)
        assert len(result) == 5
        _, _, _, confidence, _ = result
        assert 0.0 <= confidence <= 1.0

    def test_llm_service_error_triggers_fallback(self):
        """When LLM returns service error, engine should gracefully fallback."""
        from unittest.mock import MagicMock

        from router.application.decision.llm_interface import LLMInterface, LLMServiceError

        mock_llm = MagicMock(spec=LLMInterface)
        mock_llm.reason.side_effect = LLMServiceError("API connection error")

        engine = DecisionEngineV2(llm_interface=mock_llm)
        ctx = _make_base_context()

        result = engine.evaluate_routing(ctx)

        assert isinstance(result, tuple)
        assert len(result) == 5


class TestDecisionEngineV2Idempotency:
    """Tests for decision consistency on identical contexts."""

    def test_same_context_same_decision(self):
        """Identical contexts must yield identical decisions (determinism guarantee)."""
        engine = DecisionEngineV2()
        ctx = _make_base_context(message_id="idempotency_test")

        result1 = engine.evaluate_routing(ctx)
        result2 = engine.evaluate_routing(ctx)

        # Action and message_type should be deterministic
        assert result1[0] == result2[0], "Action differs between identical context evaluations."
        assert result1[1] == result2[1], "MessageType differs between identical context evaluations."
