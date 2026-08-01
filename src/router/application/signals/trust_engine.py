"""TrustEngine implementation for computing business & sender relationship trust."""

from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import ISignalCalculator


class TrustEngine(ISignalCalculator):
    """Computes relationship tie strength, group trust, and business verification score."""

    def calculate(self, context: MessageContext) -> dict[str, float]:
        """Compute trust signals for sender and business account."""
        business_trust_score = 0.0
        if context.business:
            if context.business.is_verified:
                business_trust_score += 0.6
            if context.user_business_history and context.user_business_history.has_prior_orders:
                business_trust_score += 0.4
        return {
            "business_trust_score": business_trust_score,
            "personal_sender_known": context.user is not None,
        }
