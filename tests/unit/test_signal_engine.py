"""Unit tests for SignalEngine orchestrator, validation, normalization, and conflict resolution."""

from router.application.signals.signal_engine import SignalEngine
from router.domain.entities.context import CoreMessageContext, MessageContext, TemporalInformation
from router.domain.entities.signal import SignalBundle
from router.domain.entities.sub_contexts import (
    BusinessContext,
    RelationshipContext,
    UserContext,
)
from router.domain.value_objects.risk_level import RiskLevel


def test_signal_engine_end_to_end_computation() -> None:
    """Test full SignalEngine pipeline execution returning a valid SignalBundle."""
    engine = SignalEngine()

    ctx = MessageContext(
        core_message=CoreMessageContext(
            message_id="msg_test_100",
            raw_text_content="Emergency! Your bank OTP is 492019. Valid 5 mins.",
            cleaned_text="emergency your bank otp is 492019 valid 5 mins",
            message_type="TEXT",
            char_count=50,
            word_count=8,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        ),
        sender=UserContext(
            user_id="user_bank",
            display_name="Official Bank",
            phone_number="+1800123456",
            user_type="BUSINESS",
            registration_timestamp=0,
            account_age_days=1000,
            preferred_language="en",
            timezone="UTC",
            is_verified=True,
            is_registered_user=True,
        ),
        business=BusinessContext(
            business_id="biz_bank",
            business_name="Official Bank",
            category="BANKING",
            verification_status="VERIFIED_OFFICIAL",
            support_email="support@bank.com",
            catalog_enabled=False,
            expected_sla_minutes=1,
            is_business_account=True,
        ),
        temporal_info=TemporalInformation(
            timestamp_epoch_ms=1700000000000,
            iso_timestamp="2026-08-01T12:00:00Z",
            day_of_week="SATURDAY",
            hour_of_day=14,
            is_weekend=True,
            is_working_hours=False,
        ),
    )

    bundle = engine.compute_signals(ctx)

    assert isinstance(bundle, SignalBundle)
    assert bundle.metadata.message_id == "msg_test_100"
    assert bundle.metadata.calculation_latency_ms >= 0.0
    assert 0.0 <= bundle.metadata.global_confidence <= 1.0
    assert 0.0 <= bundle.metadata.global_completeness <= 1.0

    # Urgency & Payment signal assertions
    assert bundle.urgency.payment.score == 1.0
    assert bundle.urgency.emergency.score >= 0.6
    assert bundle.urgency_score == 1.0

    # Trust signal assertions
    assert bundle.trust.business_trust_score.score == 1.0
    assert bundle.business_trust_score == 1.0


def test_conflict_arbitration_risk_trumps_urgency() -> None:
    """Test conflict arbitration rule where High Scam Risk suppresses Urgency confidence."""
    engine = SignalEngine()

    ctx_phishing = MessageContext(
        core_message=CoreMessageContext(
            message_id="msg_phish_001",
            raw_text_content="SOS Emergency! Your bank account is blocked. Share your 6-digit OTP code to verify credential immediately http://phish.scam",
            cleaned_text="sos emergency your bank account is blocked share your 6-digit otp code to verify credential immediately http phish scam",
            message_type="TEXT",
            char_count=120,
            word_count=18,
            contains_links=True,
            contains_phone_numbers=False,
            is_forwarded=True,
            forward_count=10,
            is_frequently_forwarded=True,
        ),
        sender=UserContext(
            user_id="unknown_phisher",
            display_name="Unknown",
            phone_number="+19990001111",
            user_type="INDIVIDUAL",
            registration_timestamp=0,
            account_age_days=1,
            preferred_language="en",
            timezone="UTC",
            is_verified=False,
            is_registered_user=False,
        ),
        relationship=RelationshipContext(relationship_type="PEER_TO_PEER", is_contacts_saved=False),
    )

    bundle = engine.compute_signals(ctx_phishing)

    # Risk level must be CRITICAL
    assert bundle.risk_level == RiskLevel.CRITICAL
    assert bundle.risk.scam.score >= 0.7

    # Urgency emergency confidence must be suppressed to 0.20 due to scam conflict arbitration rule
    assert bundle.urgency.emergency.confidence == 0.20
    assert "suppressed" in bundle.urgency.emergency.explainability.rationale.lower()


def test_short_circuit_on_corrupted_context() -> None:
    """Test short-circuit protocol when context completeness is extremely low (< 0.20)."""
    engine = SignalEngine()

    # Empty context with missing ID and missing sender
    corrupted_ctx = MessageContext(
        core_message=CoreMessageContext(
            message_id="",
            raw_text_content="",
            cleaned_text="",
            message_type="TEXT",
            char_count=0,
            word_count=0,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )

    bundle = engine.compute_signals(corrupted_ctx)

    assert bundle.metadata.global_confidence == 0.10
    assert bundle.metadata.global_completeness < 0.30
