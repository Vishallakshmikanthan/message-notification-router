"""Abstract Agent Ports & Multi-Agent Architecture Interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Mapping

from router.domain.entities.context import MessageContext


class IAgent(ABC):
    """Abstract Micro-Agent Base Contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return unique agent identification string."""
        ...

    @abstractmethod
    async def run(self, context: MessageContext, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute agent specialized micro-task asynchronously."""
        ...


class IRouterAgent(IAgent):
    """Abstract Master Orchestrator Router Agent Contract."""

    ...


class ISafetyAgent(IAgent):
    """Abstract Security & Injection Guard Safety Agent Contract."""

    ...


class IEvidenceAgent(IAgent):
    """Abstract Context & Memory Grounding Evidence Agent Contract."""

    ...


class IConfidenceAgent(IAgent):
    """Abstract Uncertainty Estimator Confidence Agent Contract."""

    ...


class IClassifierAgent(IAgent):
    """Abstract LLM Classifier Agent Contract."""

    ...


class IAgentOrchestrator(ABC):
    """Abstract Multi-Agent System Graph Orchestrator Contract."""

    @abstractmethod
    async def execute_graph(self, context: MessageContext) -> Mapping[str, Any]:
        """Execute full micro-agent topology graph for message evaluation context."""
        ...
