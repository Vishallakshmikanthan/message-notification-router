"""ConfidenceCalibrator implementation for adjusting confidence scores based on context alignment."""

from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle


class ConfidenceCalibrator:
    """Calibrates LLM raw confidence outputs using pre-computed analytical signal agreement."""

    def calibrate(
        self,
        raw_confidence: float,
        signals: SignalBundle | None,
        context: MessageContext,
        is_hard_filter: bool = False,
    ) -> float:
        """Calibrate confidence score guaranteed not to exceed 0.97 and reflect sparse context."""
        if is_hard_filter:
            return 0.95

        calibrated = raw_confidence
        if signals:
            if signals.completeness_score < 0.6:
                calibrated = min(calibrated, 0.65)

        # Cap confidence - never return 1.0 per architectural rules
        return round(min(0.97, max(0.10, calibrated)), 2)
