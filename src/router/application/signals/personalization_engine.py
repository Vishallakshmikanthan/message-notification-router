"""PersonalizationEngine implementation dynamically adapting base signals to match user preferences."""

from typing import Dict

from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalValue

logger = get_logger(__name__)

GREETING_WORDS = {"hi", "hello", "good morning", "good evening", "hey", "good afternoon", "gm", "gn"}


class UserBehaviourCalculator(BaseSignalCalculator):
    """Aggregates composite user activity state and current engagement readiness."""

    def get_name(self) -> str:
        return "user_behaviour_score"

    def get_category(self) -> str:
        return "personalization"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        open_rate = context.notification_behaviour.historical_open_rate or 0.5
        score = min(1.0, open_rate)

        return self.create_signal_value(
            score=score,
            confidence=0.80,
            raw_value=score,
            primary_driver="user_activity_state",
            rationale=f"User behaviour score {score:.2f}.",
        )


class UserPreferencesCalculator(BaseSignalCalculator):
    """Measures alignment of incoming context with explicit user choices (favorites, muted)."""

    def get_name(self) -> str:
        return "user_preference_alignment"

    def get_category(self) -> str:
        return "personalization"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_muted = (
            context.group.sender_is_muted_in_group
            or getattr(context, "group_is_muted_by_user", False)
            or (context.group_member is not None and getattr(context.group_member, "is_muted", False))
            or getattr(context, "group_muted", False)
        )
        if is_muted:
            score = 0.0
            driver = "explicitly_muted_conversation"
        else:
            score = 0.50
            driver = "neutral_baseline"

        return self.create_signal_value(
            score=score,
            confidence=0.90 if is_muted else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"User preference alignment score {score:.2f}.",
            contributing_factors={"is_muted": 1.0 if is_muted else 0.0},
        )


class QuietHoursCalculator(BaseSignalCalculator):
    """Measures degree of overlap with recipient's scheduled quiet window."""

    def get_name(self) -> str:
        return "quiet_hours_active"

    def get_category(self) -> str:
        return "temporal"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_quiet = getattr(context, "is_quiet_hours", False) or context.behaviour_stats.receiver_quiet_hours_active
        score = 1.0 if is_quiet else 0.0

        return self.create_signal_value(
            score=score,
            confidence=0.95,
            raw_value=score,
            primary_driver="quiet_hours_active" if is_quiet else "quiet_hours_inactive",
            rationale=f"Quiet hours active score {score:.2f}.",
        )


class GroupImportanceCalculator(BaseSignalCalculator):
    """Evaluates personal importance of target group to recipient based on role & mentions."""

    def get_name(self) -> str:
        return "group_importance"

    def get_category(self) -> str:
        return "group"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_group = context.conversation.is_group_chat or context.group.group_id != "NONE"
        if not is_group:
            score = 0.0
            driver = "not_group_chat"
            is_admin = False
            is_muted = False
        else:
            is_admin = (
                context.group.sender_role.upper() == "ADMIN"
                or getattr(context, "is_admin_message", False)
                or (context.group_member is not None and getattr(context.group_member, "is_admin", False))
            )
            is_muted = (
                context.group.sender_is_muted_in_group
                or getattr(context, "group_is_muted_by_user", False)
                or (context.group_member is not None and getattr(context.group_member, "is_muted", False))
                or getattr(context, "group_muted", False)
            )
            text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
            has_mention = "@" in text

            score = min(
                1.0,
                0.3 * (1.0 if is_admin else 0.0)
                + 0.5 * (1.0 if has_mention else 0.0)
                + (0.0 if is_muted else 0.4),
            )
            driver = "group_admin_and_mentions" if has_mention or is_admin else "standard_group"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if is_group else 1.0,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Group importance score {score:.2f}.",
            contributing_factors={
                "is_admin": 1.0 if is_admin else 0.0,
                "is_muted": 1.0 if is_muted else 0.0,
            },
        )


class DirectMentionCalculator(BaseSignalCalculator):
    """Detects presence of @mention targeting recipient in group chats."""

    def get_name(self) -> str:
        return "direct_mention"

    def get_category(self) -> str:
        return "group"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        has_mention = "@" in text
        is_admin = (
            context.group.sender_role.upper() == "ADMIN"
            or getattr(context, "is_admin_message", False)
            or (context.group_member is not None and getattr(context.group_member, "is_admin", False))
        )
        score = 1.0 if has_mention else 0.0

        return self.create_signal_value(
            score=score,
            confidence=0.95 if has_mention else 0.70,
            raw_value=score,
            primary_driver="direct_user_mention" if has_mention else "no_mention",
            rationale=f"Direct mention score {score:.2f}.",
            contributing_factors={"is_admin": 1.0 if is_admin else 0.0},
        )


class MediaImportanceCalculator(BaseSignalCalculator):
    """Evaluates information density and value of attached image, voice note, or document."""

    def get_name(self) -> str:
        return "media_importance"

    def get_category(self) -> str:
        return "media"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        has_media = context.media.has_media or bool(context.media_ocr_text) or bool(context.voice_transcript)
        if not has_media:
            score = 0.0
            driver = "no_media_payload"
        else:
            ocr_text = context.media.ocr_extracted_text or context.media_ocr_text or ""
            voice_dur = context.media.voice_duration_seconds or context.voice_duration_seconds or 0.0

            if ocr_text:
                score = min(1.0, 0.4 + 0.005 * len(ocr_text))
                driver = "ocr_text_density"
            elif voice_dur > 0:
                score = min(1.0, 0.3 + 0.01 * voice_dur)
                driver = "voice_duration_density"
            else:
                score = 0.30
                driver = "generic_media_attachment"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if has_media else 1.0,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Media importance score {score:.2f}.",
        )


class ConversationImportanceCalculator(BaseSignalCalculator):
    """Measures contextual priority of active ongoing conversation thread."""

    def get_name(self) -> str:
        return "conversation_importance"

    def get_category(self) -> str:
        return "conversation"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        burst = context.conversation.burst_message_count
        score = min(1.0, 0.3 + 0.1 * min(burst, 7))

        return self.create_signal_value(
            score=score,
            confidence=0.80,
            raw_value=score,
            primary_driver="active_thread_momentum",
            rationale=f"Conversation importance score {score:.2f}.",
        )


class CommercialIntentCalculator(BaseSignalCalculator):
    """Detects sales, promotional, or commercial service intent."""

    def get_name(self) -> str:
        return "commercial_intent"

    def get_category(self) -> str:
        return "business"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_biz = context.business.is_business_account or context.business.category != "NON_BUSINESS"
        score = 0.80 if is_biz else 0.0

        return self.create_signal_value(
            score=score,
            confidence=0.85,
            raw_value=score,
            primary_driver="business_sender" if is_biz else "peer_message",
            rationale=f"Commercial intent score {score:.2f}.",
        )


class TransactionalIntentCalculator(BaseSignalCalculator):
    """Detects utility messages (order update, shipping, receipt, OTP)."""

    def get_name(self) -> str:
        return "transactional_intent"

    def get_category(self) -> str:
        return "business"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        is_trans = any(kw in text for kw in {"order", "shipping", "receipt", "otp", "tracking", "invoice", "confirmed"})
        score = 0.90 if is_trans else 0.10

        return self.create_signal_value(
            score=score,
            confidence=0.85 if is_trans else 0.50,
            raw_value=score,
            primary_driver="utility_transactional_keywords" if is_trans else "none",
            rationale=f"Transactional intent score {score:.2f}.",
        )


class PromotionalIntentCalculator(BaseSignalCalculator):
    """Detects marketing discount, broadcast offer, or product push."""

    def get_name(self) -> str:
        return "promotional_intent"

    def get_category(self) -> str:
        return "business"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        is_promo = any(kw in text for kw in {"off", "discount", "sale", "limited time", "buy now", "deal", "promo"})
        user_opted = True
        if context.user_business_history:
            user_opted = context.user_business_history.opted_in_promotions

        score = 0.85 if is_promo else 0.05
        return self.create_signal_value(
            score=score,
            confidence=0.85 if is_promo else 0.50,
            raw_value=score,
            primary_driver="promotional_marketing_keywords" if is_promo else "none",
            rationale=f"Promotional intent score {score:.2f}.",
            contributing_factors={"user_opted_in": 1.0 if user_opted else 0.0},
        )


class GreetingDetectionCalculator(BaseSignalCalculator):
    """Identifies low-priority conversational pleasantries ("hi", "good morning")."""

    def get_name(self) -> str:
        return "greeting_detection_score"

    def get_category(self) -> str:
        return "personalization"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        word_count = context.core_message.word_count or len((context.message_text or "").split())
        text = (context.core_message.cleaned_text or context.message_text or "").strip().lower()

        if word_count <= 3 and text in GREETING_WORDS:
            score = 1.0
            driver = "isolated_greeting"
        else:
            score = 0.0
            driver = "substantive_message"

        return self.create_signal_value(
            score=score,
            confidence=0.95,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Greeting detection score {score:.2f}.",
        )


class RelevanceScoreCalculator(BaseSignalCalculator):
    """Estimates contextual interest and importance of topic/sender to recipient."""

    def get_name(self) -> str:
        return "relevance_score"

    def get_category(self) -> str:
        return "personalization"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        open_rate = context.notification_behaviour.historical_open_rate or 0.5
        history_count = context.history.historical_message_count
        score = min(1.0, 0.5 * open_rate + 0.3 * min(1.0, history_count / 50.0) + 0.2 * 0.5)

        return self.create_signal_value(
            score=score,
            confidence=0.80,
            raw_value=score,
            primary_driver="contextual_relevance",
            rationale=f"Relevance score {score:.2f}.",
        )


class HistoricalOpenRateCalculator(BaseSignalCalculator):
    """Calculates historical fraction of sender's alerts opened by recipient."""

    def get_name(self) -> str:
        return "historical_open_rate"

    def get_category(self) -> str:
        return "history"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        score = context.notification_behaviour.historical_open_rate
        if score <= 0.0 and context.user and hasattr(context.user, "open_rate"):
            score = context.user.open_rate or 0.5

        return self.create_signal_value(
            score=score,
            confidence=0.80 if score > 0 else 0.40,
            raw_value=score,
            primary_driver="historical_open_rate",
            rationale=f"Historical open rate score {score:.2f}.",
        )


class HistoricalReplyRateCalculator(BaseSignalCalculator):
    """Calculates historical fraction of sender's alerts answered by recipient."""

    def get_name(self) -> str:
        return "historical_reply_rate"

    def get_category(self) -> str:
        return "history"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        open_rate = context.notification_behaviour.historical_open_rate or 0.5
        score = open_rate * 0.6

        return self.create_signal_value(
            score=score,
            confidence=0.75,
            raw_value=score,
            primary_driver="historical_reply_rate",
            rationale=f"Historical reply rate score {score:.2f}.",
        )


class PersonalizationEngine(BaseSignalCalculator):
    """Engine coordinating all personalization signal calculations."""

    def __init__(self) -> None:
        """Initialize personalization calculators."""
        self.calculators = [
            UserBehaviourCalculator(),
            UserPreferencesCalculator(),
            QuietHoursCalculator(),
            GroupImportanceCalculator(),
            DirectMentionCalculator(),
            MediaImportanceCalculator(),
            ConversationImportanceCalculator(),
            CommercialIntentCalculator(),
            TransactionalIntentCalculator(),
            PromotionalIntentCalculator(),
            GreetingDetectionCalculator(),
            RelevanceScoreCalculator(),
            HistoricalOpenRateCalculator(),
            HistoricalReplyRateCalculator(),
        ]

    def get_name(self) -> str:
        return "personalization_engine"

    def get_category(self) -> str:
        return "personalization"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        results = {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
        return results["user_preference_alignment"]

    def calculate_all(self, context: MessageContext) -> Dict[str, SignalValue]:
        """Compute dictionary mapping each personalization signal name to its SignalValue."""
        return {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
