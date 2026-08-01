"""SignalValidator implementation for pre-computing context integrity."""

from router.domain.entities.context import MessageContext


class SignalValidator:
    """Pre-checks incoming MessageContext schema completeness for signal computation."""

    def validate_pre_check(self, context: MessageContext) -> float:
        """Calculate context metadata completeness score (0.0 - 1.0)."""
        score = 0.5  # Base score for core fields
        if context.user:
            score += 0.2
        if context.group or context.business:
            score += 0.2
        if context.media_ocr_text or context.voice_transcript:
            score += 0.1
        return min(1.0, score)
