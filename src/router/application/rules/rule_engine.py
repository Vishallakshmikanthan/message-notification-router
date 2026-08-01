"""RuleEngine implementation implementing IRuleEngine contract."""

from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle
from router.domain.ports.signal_ports import IRuleEngine
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction
from router.domain.value_objects.risk_level import RiskLevel

logger = get_logger(__name__)


class RuleEngine(IRuleEngine):
    """Executes rule-based hard filters and deterministic safety overrides."""

    def evaluate(
        self, signals: SignalBundle, context: MessageContext
    ) -> tuple[NotificationAction, MessageType, str, float] | None:
        """Evaluate hard filter logic over signals and message context.

        Returns (action, message_type, reason, confidence=0.95) if hard filter fires,
        or None if pass-through to LLM reasoning engine.
        """
        # Rule 1: Safety Critical Scam Override
        if signals.risk_level == RiskLevel.CRITICAL or signals.scam_keyword_score >= 0.8:
            logger.info("Hard filter fired: SCAM detection", message_id=context.message_id)
            return (
                NotificationAction.MUTE,
                MessageType.SCAM,
                "Message identified as high-risk scam or financial fraud pattern.",
                0.95,
            )

        # Rule 2: Deep Forward Chain Spam Override
        if signals.forward_chain_depth > 5 and signals.risk_level != RiskLevel.NONE:
            logger.info("Hard filter fired: Viral forward chain", message_id=context.message_id)
            return (
                NotificationAction.MUTE,
                MessageType.FORWARD,
                "Unverified message forwarded multiple times across groups.",
                0.95,
            )

        # Rule 3: Explicit User Group Mute Override
        if signals.group_is_muted_by_user and not signals.urgency_keywords_present:
            logger.info("Hard filter fired: Group muted by user", message_id=context.message_id)
            return (
                NotificationAction.MUTE,
                MessageType.UNKNOWN,
                "Group notifications are explicitly muted by user.",
                0.95,
            )

        # Rule 4: Quiet Hours DND Non-Urgent Override
        if signals.is_quiet_hours and not signals.urgency_keywords_present:
            logger.info("Hard filter fired: Quiet hours DND override", message_id=context.message_id)
            return (
                NotificationAction.DIGEST,
                MessageType.UNKNOWN,
                "Non-urgent notification held during user DND quiet hours window.",
                0.95,
            )

        # Pass-through to LLM reasoning engine
        return None
