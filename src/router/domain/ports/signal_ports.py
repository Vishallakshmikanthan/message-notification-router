"""Abstract Signal, Rule Engine, and Decision Engine Interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Mapping

from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction


class ISignalCalculator(ABC):
    """Abstract Signal Calculator interface."""

    @abstractmethod
    def calculate(self, context: MessageContext) -> Mapping[str, Any]:
        """Compute signals for given message context."""
        ...


class ISignalEngine(ABC):
    """Abstract Signal Computation Engine interface."""

    @abstractmethod
    def compute_signals(self, context: MessageContext) -> SignalBundle:
        """Compute and return complete SignalBundle for message context."""
        ...


class IRuleEngine(ABC):
    """Abstract Rule-Based Hard Filter Safety Override Engine interface."""

    @abstractmethod
    def evaluate(
        self, signals: SignalBundle, context: MessageContext
    ) -> tuple[NotificationAction, MessageType, str, float] | None:
        """Evaluate deterministic safety & quiet hour override rules.

        Returns (action, message_type, reason, confidence) if hard filter fires,
        or None if pass-through to LLM reasoning.
        """
        ...


class IDecisionEngine(ABC):
    """Abstract Decision Engine interface."""

    @abstractmethod
    def evaluate_routing(
        self, context: MessageContext
    ) -> tuple[NotificationAction, MessageType, str, float, list[str]]:
        """Evaluate routing decision for given context.

        Returns (action, message_type, reason, calibrated_confidence, evidence_ids).
        """
        ...
