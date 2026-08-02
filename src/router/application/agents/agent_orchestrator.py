"""AgentOrchestrator implementation implementing IAgentOrchestrator contract.

Executes the full micro-agent topology DAG asynchronously as specified in
agent_architecture.md §2 & §3:
  Router → Safety → Parallel (Evidence, Confidence) → Classifier → (Critic) → Verifier → OutputFormatter
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from router.application.agents.classifier_agent import ClassifierAgent
from router.application.agents.confidence_agent import ConfidenceAgent
from router.application.agents.critic_agent import CriticAgent
from router.application.agents.evidence_agent import EvidenceAgent
from router.application.agents.output_formatter_agent import OutputFormatterAgent
from router.application.agents.router_agent import RouterAgent
from router.application.agents.safety_agent import SafetyAgent
from router.application.agents.verifier_agent import VerifierAgent
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IAgentOrchestrator

logger = get_logger(__name__)


class AgentOrchestrator(IAgentOrchestrator):
    """Executes full micro-agent topology DAG asynchronously."""

    def __init__(self) -> None:
        """Initialize all 8 micro-agent instances."""
        self.router_agent = RouterAgent()
        self.safety_agent = SafetyAgent()
        self.evidence_agent = EvidenceAgent()
        self.confidence_agent = ConfidenceAgent()
        self.classifier_agent = ClassifierAgent()
        self.critic_agent = CriticAgent()
        self.verifier_agent = VerifierAgent()
        self.output_formatter_agent = OutputFormatterAgent()

    async def execute_graph(self, context: MessageContext) -> Mapping[str, Any]:
        """Execute full micro-agent workflow graph for incoming message context.

        DAG Flow:
        1. Router Agent (Node 0)
        2. Safety Agent (Node 1)
        3. Parallel Signal Extraction (Node 2A Evidence & Node 2B Confidence)
        4. Classifier Agent (Node 3)
        5. Critic Agent (Node 4A - conditional)
        6. Verifier Agent (Node 4B - conditional)
        7. Output Formatter Agent (Node 5 - terminal)
        """
        logger.debug("Executing micro-agent workflow graph", message_id=context.message_id)

        # Node 0: Router Agent
        plan = await self.router_agent.execute(context, {})

        # Node 1: Safety Agent
        safety_res = await self.safety_agent.execute(context, plan)

        # Node 2: Parallel Signal Processing (asyncio.gather)
        evidence_task = self.evidence_agent.execute(context, safety_res)
        confidence_task = self.confidence_agent.execute(context, safety_res)
        evidence_res, confidence_res = await asyncio.gather(evidence_task, confidence_task)

        # Node 3: Classifier Agent
        classifier_inputs = {
            **safety_res,
            **evidence_res,
            **confidence_res,
        }
        classifier_res = await self.classifier_agent.execute(context, classifier_inputs)

        # Node 4A: Critic Agent (Conditional)
        critic_inputs = {**classifier_inputs, **classifier_res}
        critic_res = await self.critic_agent.execute(context, critic_inputs)

        # Node 4B: Verifier Agent (Conditional)
        verifier_inputs = {**critic_inputs, **critic_res}
        verifier_res = await self.verifier_agent.execute(context, verifier_inputs)

        # Node 5: Output Formatter Agent (Terminal)
        final_inputs = {**verifier_inputs, **verifier_res}
        final_response = await self.output_formatter_agent.execute(context, final_inputs)

        return final_response
