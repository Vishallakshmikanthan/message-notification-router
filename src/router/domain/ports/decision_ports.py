"""Abstract Port Interfaces for the Decision Intelligence Layer (Phase 7).

All interfaces follow the dependency-inversion principle: high-level
orchestration components depend on these abstractions, not concrete
implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple

from router.domain.entities.context import MessageContext
from router.domain.entities.decision_models import (
    CalibratedDecision,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    DecisionResult,
    ReasonerInputFrame,
    ReasoningOutput,
    RuleEvaluationResult,
    VerificationResult,
)
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.signal import SignalBundle
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction


class IDecisionFactory(ABC):
    """Abstract factory that constructs a validated, immutable DecisionContext."""

    @abstractmethod
    def build_context(
        self,
        message_context: MessageContext,
        signal_bundle: SignalBundle,
        evidence_bundle: EvidenceBundle,
    ) -> DecisionContext:
        """Aggregate upstream layer outputs into a single DecisionContext frame.

        Args:
            message_context: Enriched message context from Context Engine.
            signal_bundle: Computed signal bundle from Signal Engine.
            evidence_bundle: Retrieved evidence bundle from Retrieval Engine.

        Returns:
            Immutable, validated DecisionContext ready for engine consumption.
        """
        ...


class IRuleEngineV2(ABC):
    """Abstract Rule Engine interface for deterministic Level 0 / Level 1 evaluation."""

    @abstractmethod
    def evaluate(self, context: DecisionContext) -> RuleEvaluationResult:
        """Evaluate the full deterministic rule catalog against the DecisionContext.

        Args:
            context: Validated DecisionContext.

        Returns:
            RuleEvaluationResult indicating whether a rule fired and bypass_llm status.
        """
        ...


class IDecisionOrchestrator(ABC):
    """Abstract Decision Orchestrator controlling branching and frame construction."""

    @abstractmethod
    def prepare_reasoner_frame(self, context: DecisionContext) -> ReasonerInputFrame:
        """Construct the structured LLM input frame from the DecisionContext.

        Args:
            context: Validated DecisionContext.

        Returns:
            Structured ReasonerInputFrame for consumption by LLMInterface.
        """
        ...


class ILLMInterface(ABC):
    """Abstract LLM Reasoning Service interface.

    Wraps the actual LLM invocation without exposing prompt strings.
    All inputs and outputs are strictly typed.
    """

    @abstractmethod
    def reason(self, frame: ReasonerInputFrame) -> ReasoningOutput:
        """Invoke the LLM reasoner with a structured context frame.

        Args:
            frame: Typed input frame with message payload, signals, and evidence.

        Returns:
            Structured ReasoningOutput with proposed action and rationale.

        Raises:
            LLMTimeoutError: If invocation exceeds 250ms SLA.
            LLMServiceError: If the LLM service returns an unexpected error.
        """
        ...


class IConfidenceEngine(ABC):
    """Abstract Confidence Engine for calibration and uncertainty quantification."""

    @abstractmethod
    def calibrate(
        self,
        rule_result: Optional[RuleEvaluationResult],
        reasoning_output: Optional[ReasoningOutput],
        context: DecisionContext,
    ) -> CalibratedDecision:
        """Compute calibrated posterior confidence from raw inputs.

        Implements the full formula:
          C_base = C_raw + S_adj + E_adj + H_adj
        Then applies temperature-scaled sigmoid calibration.

        Args:
            rule_result: Non-None if deterministic rule fired.
            reasoning_output: Non-None if LLM path was executed.
            context: Full DecisionContext for signal agreement analysis.

        Returns:
            CalibratedDecision with posterior confidence and breakdown.
        """
        ...


class IDecisionValidator(ABC):
    """Abstract 5-pass output validator for DecisionResult quality gates."""

    @abstractmethod
    def validate(
        self,
        decision: CalibratedDecision,
        context: DecisionContext,
    ) -> VerificationResult:
        """Run 5-pass validation suite on the calibrated decision.

        Passes:
          1. Schema validation (required fields, type checks).
          2. Allowed values & boundary checks.
          3. Reasoning consistency validation.
          4. Evidence grounding verification.
          5. Confidence threshold verification.

        Args:
            decision: CalibratedDecision to validate.
            context: DecisionContext for grounding cross-check.

        Returns:
            VerificationResult with is_valid flag and error details.
        """
        ...


class IDecisionLogger(ABC):
    """Abstract async Decision Logger for audit traces and telemetry."""

    @abstractmethod
    def log_decision(
        self,
        decision_result: DecisionResult,
        context: DecisionContext,
    ) -> None:
        """Asynchronously record a structured decision audit trace.

        Args:
            decision_result: The validated final DecisionResult.
            context: The DecisionContext used to generate the result.
        """
        ...


class IOutputFormatter(ABC):
    """Abstract Output Formatter mapping DecisionResult to the IDecisionEngine return tuple."""

    @abstractmethod
    def format(
        self,
        decision_result: DecisionResult,
    ) -> Tuple[NotificationAction, MessageType, str, float, List[str]]:
        """Map a DecisionResult to the legacy 5-tuple IDecisionEngine output contract.

        Args:
            decision_result: The fully validated and logged DecisionResult.

        Returns:
            5-tuple: (action, message_type, reason, confidence, evidence_ids).
        """
        ...
