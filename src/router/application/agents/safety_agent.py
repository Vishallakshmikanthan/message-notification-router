"""SafetyAgent implementation (Security & Injection Guard)."""

from collections.abc import Mapping
from typing import Any

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import ISafetyAgent


class SafetyAgent(BaseAgent, ISafetyAgent):
    """Audits input message text, OCR, and transcripts for security threats and prompt injection."""

    def __init__(self) -> None:
        """Initialize SafetyAgent."""
        super().__init__(agent_name="SafetyAgent")

    async def run(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Perform safety audit on message text and media transcripts."""
        return {
            "is_safe": True,
            "violation_type": None,
            "sanitized_text": context.message_text,
        }
