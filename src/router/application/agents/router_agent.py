"""RouterAgent implementation (Master Orchestrator)."""

from collections.abc import Mapping
from typing import Any

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IRouterAgent


class RouterAgent(BaseAgent, IRouterAgent):
    """Evaluates context risk and constructs execution plan DAG for incoming notifications."""

    def __init__(self) -> None:
        """Initialize RouterAgent."""
        super().__init__(agent_name="RouterAgent")

    async def run(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Construct execution plan DAG for message context."""
        return {
            "tier_level": 1,
            "agents_to_invoke": ["SafetyAgent", "EvidenceAgent", "ConfidenceAgent", "ClassifierAgent"],
            "is_bypass": False,
        }
