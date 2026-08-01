"""RiskEngine implementation for evaluating spam, scam, and safety hazard risk."""

from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import ISignalCalculator
from router.domain.value_objects.risk_level import RiskLevel

SCAM_KEYWORDS = {"lottery", "prize", "otp", "click here", "wire transfer", "bank block", "banned"}


class RiskEngine(ISignalCalculator):
    """Evaluates spam probability, scam patterns, forward virality, and unverified sender hazard."""

    def calculate(self, context: MessageContext) -> dict[str, float | str | bool]:
        """Compute scam, spam, and categorical risk level signals."""
        text_lower = context.message_text.lower()
        scam_hits = sum(1 for kw in SCAM_KEYWORDS if kw in text_lower)
        scam_score = min(1.0, scam_hits * 0.4)

        if context.media_ocr_text:
            ocr_hits = sum(1 for kw in SCAM_KEYWORDS if kw in context.media_ocr_text.lower())
            scam_score = max(scam_score, min(1.0, ocr_hits * 0.4))

        risk_level = RiskLevel.NONE
        if scam_score >= 0.8:
            risk_level = RiskLevel.CRITICAL
        elif scam_score >= 0.5 or context.forwarded_count > 5:
            risk_level = RiskLevel.HIGH
        elif scam_score > 0.0:
            risk_level = RiskLevel.MEDIUM

        return {
            "scam_keyword_score": scam_score,
            "forward_chain_depth": context.forwarded_count,
            "risk_level": risk_level,
            "unverified_business_flag": (
                context.business is not None and not context.business.is_verified
            ),
        }
