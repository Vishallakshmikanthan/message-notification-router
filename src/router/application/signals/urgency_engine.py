"""UrgencyEngine implementation for evaluating message urgency and crisis keywords."""

from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import ISignalCalculator

URGENCY_KEYWORDS = {"urgent", "emergency", "hospital", "help", "asap", "alert", "immediately"}


class UrgencyEngine(ISignalCalculator):
    """Evaluates time sensitivity, emergency triggers, and critical keywords."""

    def calculate(self, context: MessageContext) -> dict[str, float | bool]:
        """Compute urgency signals for text and transcripts."""
        text_lower = context.message_text.lower()
        has_urgency = any(kw in text_lower for kw in URGENCY_KEYWORDS)

        if context.voice_transcript:
            has_urgency = has_urgency or any(
                kw in context.voice_transcript.lower() for kw in URGENCY_KEYWORDS
            )

        return {
            "urgency_keywords_present": has_urgency,
            "urgency_score": 0.9 if has_urgency else 0.1,
        }
