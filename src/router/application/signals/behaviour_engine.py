"""BehaviourEngine implementation modeling user alert load, engagement velocity, and dismissal habits."""

import math
from typing import Dict

from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalValue

logger = get_logger(__name__)


class NotificationFatigueCalculator(BaseSignalCalculator):
    """Quantifies user alert overload and current notification pressure."""

    def get_name(self) -> str:
        return "notification_fatigue"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        notifs_24h = context.notification_behaviour.user_daily_notification_volume or context.notification_load_today
        cap = context.notification_behaviour.daily_notification_cap or 50
        notifs_1h = int(notifs_24h * 0.2)  # Estimate 1-hour burst fraction if hourly not tracked

        score = min(1.0, 0.6 * (notifs_1h / 10.0) + 0.4 * (notifs_24h / float(cap)))
        conf = 0.85 if notifs_24h > 0 else 0.50

        return self.create_signal_value(
            score=score,
            confidence=conf,
            raw_value=score,
            primary_driver="alert_overload" if score > 0.6 else "normal_load",
            rationale=f"Notification fatigue score {score:.2f} (volume_24h={notifs_24h}, cap={cap}).",
            contributing_factors={"volume_today": float(notifs_24h)},
        )


class ReadingResponsivenessCalculator(BaseSignalCalculator):
    """Estimates expected speed with which user will open and read a message from this sender."""

    def get_name(self) -> str:
        return "reading_responsiveness"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        open_rate = context.notification_behaviour.historical_open_rate
        if open_rate <= 0.0 and context.user and hasattr(context.user, "open_rate"):
            open_rate = context.user.open_rate or 0.5

        median_latency_sec = context.notification_behaviour.historical_avg_response_seconds or 1800.0
        score = 0.6 * open_rate + 0.4 * math.exp(-median_latency_sec / 3600.0)

        return self.create_signal_value(
            score=score,
            confidence=0.80 if open_rate > 0 else 0.40,
            raw_value=score,
            primary_driver="historical_open_velocity",
            rationale=f"Reading responsiveness score {score:.2f} (open_rate={open_rate:.2f}).",
        )


class ReplyVelocityCalculator(BaseSignalCalculator):
    """Measures historical propensity to reply to sender and average response speed."""

    def get_name(self) -> str:
        return "reply_velocity"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        open_rate = context.notification_behaviour.historical_open_rate or 0.4
        reply_rate = open_rate * 0.7
        avg_resp_sec = context.notification_behaviour.historical_avg_response_seconds or 3600.0

        score = 0.7 * reply_rate + 0.3 * math.exp(-avg_resp_sec / 14400.0)
        return self.create_signal_value(
            score=score,
            confidence=0.75,
            raw_value=score,
            primary_driver="reply_speed",
            rationale=f"Reply velocity score {score:.2f}.",
        )


class DismissPropensityCalculator(BaseSignalCalculator):
    """Predicts probability of recipient swiping away alert without opening thread."""

    def get_name(self) -> str:
        return "dismiss_propensity"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        # Default category baseline dismiss rate
        sender_dismiss = 0.15
        cat_dismiss = 0.15
        if context.business.is_business_account:
            cat_dismiss = 0.40

        score = 0.6 * sender_dismiss + 0.4 * cat_dismiss
        return self.create_signal_value(
            score=score,
            confidence=0.70,
            raw_value=score,
            primary_driver="dismiss_history",
            rationale=f"Dismiss propensity score {score:.2f}.",
        )


class IgnorePropensityCalculator(BaseSignalCalculator):
    """Predicts probability of user leaving message unread indefinitely."""

    def get_name(self) -> str:
        return "ignore_propensity"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        days_unread = context.history.days_since_last_interaction
        unread_ratio = min(1.0, days_unread / 30.0) if days_unread > 0 else 0.1

        score = min(1.0, 0.7 * unread_ratio + 0.3 * min(1.0, days_unread / 30.0))
        return self.create_signal_value(
            score=score,
            confidence=0.75,
            raw_value=score,
            primary_driver="unread_accumulation",
            rationale=f"Ignore propensity score {score:.2f} (days_since_interaction={days_unread}).",
        )


class TimeOfDayAffinityCalculator(BaseSignalCalculator):
    """Measures alignment of current hour with user's active historical response window."""

    def get_name(self) -> str:
        return "time_of_day_affinity"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        hour = context.temporal_info.hour_of_day
        if 8 <= hour <= 22:
            score = 0.90
            driver = "active_daytime_hours"
        elif 6 <= hour < 8 or 22 < hour <= 23:
            score = 0.50
            driver = "shoulder_hours"
        else:
            score = 0.05
            driver = "late_night_sleep_hours"

        return self.create_signal_value(
            score=score,
            confidence=0.90,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Time of day affinity score {score:.2f} for hour {hour}.",
        )


class WeekendResponsivenessCalculator(BaseSignalCalculator):
    """Evaluates willingness to engage with alerts during weekend hours."""

    def get_name(self) -> str:
        return "weekend_responsiveness"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_weekend = context.temporal_info.is_weekend
        if not is_weekend:
            score = 1.0
            driver = "weekday"
        else:
            is_work = context.relationship.relationship_type.upper() == "WORK"
            score = 0.30 if is_work else 0.85
            driver = "weekend_work_suppression" if is_work else "weekend_personal"

        return self.create_signal_value(
            score=score,
            confidence=0.85,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Weekend responsiveness score {score:.2f} (is_weekend={is_weekend}).",
        )


class GroupEngagementCalculator(BaseSignalCalculator):
    """Quantifies user participation, reading, and response activity within target group."""

    def get_name(self) -> str:
        return "group_engagement"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_group = context.conversation.is_group_chat or context.group.group_id != "NONE"
        if not is_group:
            score = 1.0
            driver = "not_group_chat"
        else:
            activity = 0.5  # Neutral default group activity
            if context.group_member:
                activity = context.group_member.activity_score
            score = activity
            driver = "group_member_activity"

        return self.create_signal_value(
            score=score,
            confidence=0.80 if is_group else 1.0,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Group engagement score {score:.2f}.",
        )


class BusinessEngagementCalculator(BaseSignalCalculator):
    """Evaluates user's historical receptivity to commercial and transactional messages."""

    def get_name(self) -> str:
        return "business_engagement"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_biz = context.business.is_business_account or context.business.category != "NON_BUSINESS"
        if not is_biz:
            score = 1.0
            driver = "not_business"
        else:
            has_prior = False
            if context.user_business_history:
                has_prior = context.user_business_history.has_prior_orders
            score = 0.80 if has_prior else 0.35
            driver = "commercial_interaction_history" if has_prior else "new_business_sender"

        return self.create_signal_value(
            score=score,
            confidence=0.80,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Business engagement score {score:.2f}.",
        )


class BehaviourEngine(BaseSignalCalculator):
    """Engine coordinating all behavioral signal calculations."""

    def __init__(self) -> None:
        """Initialize behavioral calculators."""
        self.calculators = [
            NotificationFatigueCalculator(),
            ReadingResponsivenessCalculator(),
            ReplyVelocityCalculator(),
            DismissPropensityCalculator(),
            IgnorePropensityCalculator(),
            TimeOfDayAffinityCalculator(),
            WeekendResponsivenessCalculator(),
            GroupEngagementCalculator(),
            BusinessEngagementCalculator(),
        ]

    def get_name(self) -> str:
        return "behaviour_engine"

    def get_category(self) -> str:
        return "behaviour"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        results = {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
        return results["notification_fatigue"]

    def calculate_all(self, context: MessageContext) -> Dict[str, SignalValue]:
        """Compute dictionary mapping each behavioural signal name to its SignalValue."""
        return {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
