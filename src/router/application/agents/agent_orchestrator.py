"""AgentOrchestrator implementation implementing IAgentOrchestrator contract."""

from typing import Any, Mapping

from router.application.agents.classifier_agent import ClassifierAgent
from router.application.agents.confidence_agent import ConfidenceAgent
from router.application.agents.evidence_agent import EvidenceAgent
from router.application.agents.router_agent import RouterAgent
from router.application.agents.safety_agent import SafetyAgent
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.ports.agent_ports import IAgentOrchestrator

logger = get_logger(__name__)


class AgentOrchestrator(IAgentOrchestrator):
    """Executes full micro-agent topology DAG asynchronously."""

    def __init__(self) -> None:
        """Initialize agent instances."""
        self.router_agent = RouterAgent()
        self.safety_agent = SafetyAgent()
        self.evidence_agent = EvidenceAgent()
        self.confidence_agent = ConfidenceAgent()
        self.classifier_agent = ClassifierAgent()

    async def execute_graph(self, context: MessageContext) -> Mapping[str, Any]:
        """Execute micro-agent workflow graph for incoming message context."""
        logger.debug("Executing micro-agent workflow graph", message_id=context.message_id)

        plan = await self.router_agent.execute(context, {})
        safety_res = await self.safety_agent.execute(context, plan)
        evidence_res = await self.evidence_agent.execute(context, safety_res)
        confidence_res = await self.confidence_agent.execute(context, safety_res)

        classifier_inputs = {
            **safety_res,
            **evidence_res,
            **confidence_res,
        }
        decision_res = await self.classifier_agent.execute(context, classifier_inputs)
        return decision_res
