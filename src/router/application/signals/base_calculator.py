"""Abstract base SignalCalculator class extending ISignalCalculator port."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping

from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalExplainability, SignalValue
from router.domain.ports.signal_ports import ISignalCalculator


class BaseSignalCalculator(ISignalCalculator, ABC):
    """Abstract base class for all continuous signal calculators."""

    @abstractmethod
    def get_name(self) -> str:
        """Return unique identifier name for the calculator."""
        ...

    @abstractmethod
    def get_category(self) -> str:
        """Return signal category block name (e.g., 'urgency', 'risk', 'trust')."""
        ...

    @abstractmethod
    def calculate_signal(self, context: MessageContext) -> SignalValue:
        """Compute typed SignalValue for given message context."""
        ...

    def calculate(self, context: MessageContext) -> Mapping[str, Any]:
        """Bridge to ISignalCalculator interface returning dictionary representation."""
        sig_val = self.calculate_signal(context)
        return {
            "score": sig_val.score,
            "confidence": sig_val.confidence,
            "raw_value": sig_val.explainability.raw_value,
            "primary_driver": sig_val.explainability.primary_driver,
            "rationale": sig_val.explainability.rationale,
            "contributing_factors": sig_val.explainability.contributing_factors,
            "signal_value": sig_val,
        }

    def create_signal_value(
        self,
        score: float,
        confidence: float,
        raw_value: float,
        primary_driver: str,
        rationale: str,
        contributing_factors: Dict[str, float] | None = None,
    ) -> SignalValue:
        """Helper method to construct bounded SignalValue with explainability metadata."""
        clamped_score = max(0.0, min(1.0, float(score)))
        clamped_conf = max(0.0, min(1.0, float(confidence)))
        factors = contributing_factors if contributing_factors is not None else {}
        return SignalValue(
            score=clamped_score,
            confidence=clamped_conf,
            explainability=SignalExplainability(
                raw_value=float(raw_value),
                primary_driver=str(primary_driver),
                rationale=str(rationale),
                contributing_factors=factors,
            ),
        )
