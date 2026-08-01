"""ConfidenceAgent implementation (Uncertainty Estimator)."""

from typing import Any, Mapping

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IConfidenceAgent


class ConfidenceAgent(BaseAgent, IConfidenceAgent):
    """Estimates baseline uncertainty and context completeness vector."""

    def __init__(self) -> None:
        """Initialize ConfidenceAgent."""
        super().__init__(agent_name="ConfidenceAgent")

    async def run(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Compute baseline confidence vector for routing evaluation."""
        completeness = context.signals.completeness_score if context.signals else 0.5
        return {
            "baseline_confidence": min(0.95, completeness * 0.9),
            "uncertainty_score": 1.0 - completeness,
        }
