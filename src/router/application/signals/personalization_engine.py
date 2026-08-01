"""PersonalizationEngine implementation for user-specific preference signal computation."""

from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import ISignalCalculator


class PersonalizationEngine(ISignalCalculator):
    """Computes personalized group relevance and opt-in signals."""

    def calculate(self, context: MessageContext) -> dict[str, float | bool]:
        """Compute user personalized channel relevance signals."""
        group_relevance_score = 0.5
        if context.group_member:
            group_relevance_score = context.group_member.activity_score

        user_opted_in = True
        if context.user_business_history:
            user_opted_in = context.user_business_history.opted_in_promotions

        return {
            "group_relevance_score": group_relevance_score,
            "user_opted_in": user_opted_in,
            "group_is_muted_by_user": context.group_member.is_muted if context.group_member else False,
            "is_admin_message": context.group_member.is_admin if context.group_member else False,
        }
