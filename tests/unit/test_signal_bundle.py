"""Unit tests for SignalBundle and SignalValue domain entities."""

import pytest
from dataclasses import FrozenInstanceError

from router.application.signals.signal_factory import SignalFactory
from router.domain.entities.signal import (
    SignalBundle,
    SignalExplainability,
    SignalValue,
)
from router.domain.value_objects.risk_level import RiskLevel


def test_signal_value_creation() -> None:
    """Test creation and property bounds of atomic SignalValue envelope."""
    sig = SignalFactory.create_signal_value(
        score=0.85,
        confidence=0.95,
        raw_value=0.85,
        primary_driver="test_driver",
        rationale="Test rationale description",
        contributing_factors={"factor1": 1.0},
    )

    assert sig.score == 0.85
    assert sig.confidence == 0.95
    assert sig.explainability.primary_driver == "test_driver"
    assert sig.explainability.rationale == "Test rationale description"
    assert sig.explainability.contributing_factors == {"factor1": 1.0}


def test_signal_value_immutability() -> None:
    """Test that SignalValue objects are deep-frozen and immutable."""
    sig = SignalFactory.create_null_fallback()
    with pytest.raises(FrozenInstanceError):
        sig.score = 0.5  # type: ignore[misc]


def test_signal_factory_build_bundle() -> None:
    """Test building complete SignalBundle via SignalFactory."""
    signals = {
        "emergency": SignalFactory.create_signal_value(0.9, 0.9, 0.9, "sos_kw", "SOS detected"),
        "scam": SignalFactory.create_signal_value(0.85, 0.95, 0.85, "phishing_link", "Scam detected"),
        "known_contact_score": SignalFactory.create_signal_value(1.0, 1.0, 1.0, "saved", "Contact saved"),
        "quiet_hours_active": SignalFactory.create_signal_value(1.0, 1.0, 1.0, "quiet", "Quiet hours active"),
    }

    bundle = SignalFactory.build_bundle(
        message_id="msg_123",
        all_signals=signals,
        latency_ms=5.5,
        global_confidence=0.90,
        global_completeness=0.85,
    )

    assert isinstance(bundle, SignalBundle)
    assert bundle.message_id == "msg_123"
    assert bundle.urgency.emergency.score == 0.9
    assert bundle.risk.scam.score == 0.85
    assert bundle.trust.known_contact_score.score == 1.0
    assert bundle.temporal.quiet_hours_active.score == 1.0
    assert bundle.is_quiet_hours is True
    assert bundle.risk_level == RiskLevel.CRITICAL
    assert bundle.urgency_score == 0.9
    assert bundle.completeness_score == 0.85
    assert "sos_kw" in bundle.candidate_evidence_ids
    assert "phishing_link" in bundle.candidate_evidence_ids


def test_signal_bundle_immutability() -> None:
    """Test that SignalBundle container is frozen."""
    bundle = SignalFactory.build_bundle("msg_001", {}, 2.0, 0.5, 0.5)
    with pytest.raises(FrozenInstanceError):
        bundle.metadata = None  # type: ignore[misc]
