"""SignalNormalizer implementation for mathematical scaling and conflict arbitration."""

import math
from typing import Dict

from router.core.logging.logger import get_logger
from router.domain.entities.signal import SignalExplainability, SignalValue

logger = get_logger(__name__)


class SignalNormalizer:
    """Mathematical bounding and conflict resolution engine for signal values."""

    @staticmethod
    def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Clamp float value strictly to [min_val, max_val] range."""
        return max(min_val, min(max_val, float(value)))

    @staticmethod
    def min_max_scale(value: float, min_val: float, max_val: float) -> float:
        """Apply min-max scaling to bound raw value continuously in [0.0, 1.0]."""
        if max_val <= min_val:
            return 0.0
        scaled = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, float(scaled)))

    @staticmethod
    def logistic_sigmoid(x: float, k: float = 1.0, x0: float = 0.0) -> float:
        """Apply logistic sigmoid transformation: S = 1 / (1 + e^(-k * (x - x0)))."""
        try:
            val = 1.0 / (1.0 + math.exp(-k * (x - x0)))
            return max(0.0, min(1.0, float(val)))
        except OverflowError:
            return 1.0 if x > x0 else 0.0

    @classmethod
    def normalize_signal(cls, signal: SignalValue) -> SignalValue:
        """Ensure score and confidence of signal are strictly clamped within [0.0, 1.0]."""
        bounded_score = cls.clamp(signal.score)
        bounded_conf = cls.clamp(signal.confidence)
        if bounded_score == signal.score and bounded_conf == signal.confidence:
            return signal
        return SignalValue(
            score=bounded_score,
            confidence=bounded_conf,
            explainability=signal.explainability,
        )

    @classmethod
    def resolve_conflicts(cls, signals: Dict[str, SignalValue]) -> Dict[str, SignalValue]:
        """Apply deterministic arbitration matrix for conflicting signal pairs (signal_quality.md)."""
        resolved = dict(signals)

        # 1. High Urgency vs High Scam Risk: Risk Trumps Urgency
        scam = resolved.get("scam")
        urgency_emergency = resolved.get("emergency")
        if scam and urgency_emergency:
            if scam.score >= 0.7 and urgency_emergency.score >= 0.6:
                logger.info("Conflict Arbitrated: Risk Trumps Urgency (Scam score >= 0.7)")
                # Suppress urgency confidence to 0.20
                resolved["emergency"] = SignalValue(
                    score=urgency_emergency.score,
                    confidence=0.20,
                    explainability=SignalExplainability(
                        raw_value=urgency_emergency.explainability.raw_value,
                        primary_driver=urgency_emergency.explainability.primary_driver,
                        rationale=f"{urgency_emergency.explainability.rationale} [Confidence suppressed due to high scam risk]",
                        contributing_factors=urgency_emergency.explainability.contributing_factors,
                    ),
                )

        # 2. High Relationship vs Unknown Sender Risk: Trust Trumps Unknown Sender
        relationship = resolved.get("relationship_score")
        unknown_sender = resolved.get("unknown_sender_risk")
        if relationship and unknown_sender:
            if relationship.score >= 0.85 and unknown_sender.score >= 0.8:
                logger.info("Conflict Arbitrated: Trust Trumps Unknown Sender (Relationship score >= 0.85)")
                resolved["unknown_sender_risk"] = SignalValue(
                    score=0.10,
                    confidence=unknown_sender.confidence,
                    explainability=SignalExplainability(
                        raw_value=unknown_sender.explainability.raw_value,
                        primary_driver="relationship_trust_override",
                        rationale="Unknown sender risk overridden by verified strong relationship history.",
                        contributing_factors=unknown_sender.explainability.contributing_factors,
                    ),
                )

        # 3. High Business Trust vs High Spam Score: Spam Dampening
        biz_trust = resolved.get("business_trust_score")
        spam = resolved.get("spam")
        if biz_trust and spam:
            if biz_trust.score >= 0.9 and spam.score >= 0.8:
                logger.info("Conflict Arbitrated: Spam Dampening on Business Trust")
                resolved["business_trust_score"] = SignalValue(
                    score=0.40,
                    confidence=biz_trust.confidence,
                    explainability=SignalExplainability(
                        raw_value=biz_trust.explainability.raw_value,
                        primary_driver="spam_dampening_override",
                        rationale="Business trust score dampened due to high bulk spam broadcast activity.",
                        contributing_factors=biz_trust.explainability.contributing_factors,
                    ),
                )

        return resolved
