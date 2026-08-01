"""SignalValidator implementation for pre-computing context integrity and output bundle auditing."""

from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle, SignalValue

logger = get_logger(__name__)


class SignalValidator:
    """Pre-checks incoming MessageContext schema completeness and audits output SignalBundle integrity."""

    def validate_pre_check(self, context: MessageContext) -> float:
        """Inspect MessageContext schema integrity and calculate completeness score (0.0 to 1.0)."""
        score = 0.0

        # 1. Primary identifier check
        msg_id = context.core_message.message_id or context.message_id
        if msg_id and msg_id != "NONE":
            score += 0.40
        else:
            logger.warning("Context validation pre-check missing primary message_id")

        # 2. Sender / Receiver UserContext presence
        if context.sender.user_id != "UNKNOWN_USER" or context.sender.is_registered_user:
            score += 0.20
        if context.receiver.user_id != "UNKNOWN_USER":
            score += 0.10

        # 3. Contextual Sub-entities (Group, Business, Media)
        if context.group.group_id != "NONE" or context.business.business_id != "NONE":
            score += 0.15
        if context.media.has_media or context.media_ocr_text or context.voice_transcript:
            score += 0.15

        completeness = max(0.0, min(1.0, float(score)))
        logger.debug("Context pre-check validation completed", completeness_score=completeness)
        return completeness

    def validate_signal_value(self, signal: SignalValue) -> bool:
        """Verify that a SignalValue object satisfies score bounds [0.0, 1.0] and non-empty rationale."""
        if not (0.0 <= signal.score <= 1.0):
            logger.error("Signal score out of bounds [0.0, 1.0]", score=signal.score)
            return False
        if not (0.0 <= signal.confidence <= 1.0):
            logger.error("Signal confidence out of bounds [0.0, 1.0]", confidence=signal.confidence)
            return False
        if not signal.explainability.rationale:
            logger.error("Signal explainability missing rationale")
            return False
        return True

    def validate_bundle(self, bundle: SignalBundle) -> bool:
        """Audit frozen SignalBundle for structural validity and score bounds compliance."""
        if not bundle.metadata.bundle_id:
            logger.error("SignalBundle missing bundle_id")
            return False
        if not bundle.metadata.message_id:
            logger.error("SignalBundle missing message_id")
            return False
        if not (0.0 <= bundle.metadata.global_completeness <= 1.0):
            logger.error("SignalBundle global completeness out of bounds")
            return False
        return True
