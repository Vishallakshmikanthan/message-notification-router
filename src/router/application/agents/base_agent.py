"""BaseAgent Abstract Implementation adhering to IAgent port contract."""

from abc import ABC
from collections.abc import Mapping
from typing import Any

from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IAgent

logger = get_logger(__name__)


class BaseAgent(IAgent, ABC):
    """Base Micro-Agent class providing shared logging and error isolation boundaries."""

    def __init__(self, agent_name: str) -> None:
        """Initialize BaseAgent with agent name."""
        self._name = agent_name

    @property
    def name(self) -> str:
        """Return unique agent identification string."""
        return self._name

    async def execute(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute agent with boundary logging and exception catching."""
        logger.debug("Executing agent", agent_name=self.name, message_id=context.message_id)
        try:
            return await self.run(context, inputs)
        except Exception as exc:
            logger.error("Agent execution failed", agent_name=self.name, error=str(exc))
            return {"status": "error", "error": str(exc), "agent": self.name}
