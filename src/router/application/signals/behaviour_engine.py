"""BehaviourEngine implementation for computing user reaction dynamics."""

from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import ISignalCalculator


class BehaviourEngine(ISignalCalculator):
    """Computes user engagement, notification fatigue, and reading responsiveness signals."""

    def calculate(self, context: MessageContext) -> dict[str, float]:
        """Compute user behaviour and notification fatigue signals."""
        user_engagement_score = context.user.open_rate if context.user else 0.5
        notification_fatigue_score = min(1.0, context.notification_load_today / 50.0)
        return {
            "user_engagement_score": user_engagement_score,
            "notification_fatigue_score": notification_fatigue_score,
        }
