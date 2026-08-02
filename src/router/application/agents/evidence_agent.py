"""EvidenceAgent implementation (Context & Memory Grounding)."""

from collections.abc import Mapping
from typing import Any

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IEvidenceAgent


class EvidenceAgent(BaseAgent, IEvidenceAgent):
    """Retrieves and formats historical message evidence citations for grounding LLM decisions."""

    def __init__(self) -> None:
        """Initialize EvidenceAgent."""
        super().__init__(agent_name="EvidenceAgent")

    async def run(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Retrieve evidence citations from historical trajectories."""
        candidate_ids = (
            context.signals.candidate_evidence_ids if context.signals else []
        )
        return {
            "key_citations": candidate_ids,
            "evidence_count": len(candidate_ids),
        }
