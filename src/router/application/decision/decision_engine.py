"""DecisionEngine — Top-level facade implementing the 12-Stage Decision Pipeline.

This is the central orchestration entry point of the Decision Intelligence Layer.
It implements the full 12-stage pipeline as specified in decision_flow.md, wiring
together all Phase 7 components: DecisionFactory, RuleEngineV2, DecisionOrchestrator,
LLMInterface, ConfidenceEngine, DecisionValidator, DecisionLogger, and OutputFormatter.

Decision paths:
  FAST-PATH: Rule fires → Stage 5 → Stage 9 → Stage 11 → Stage 12 (~5ms)
  STANDARD PATH: No rule → Stage 6-8 → Stage 9-12 (~250ms)
  FALLBACK PATH: LLM timeout/error → Stage 11 (fallback) → Stage 12 (~2ms)

Spec: decision_engine.md §2, decision_flow.md §1-§4.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Optional, Tuple

from router.application.decision.confidence_engine import ConfidenceEngine
from router.application.decision.decision_factory import DecisionFactory
from router.application.decision.decision_logger import DecisionLogger
from router.application.decision.decision_orchestrator import DecisionOrchestrator
from router.application.decision.decision_validator import DecisionValidator
from router.application.decision.llm_interface import (
    AnalyticReasoningEngine,
    LLMInterface,
    LLMServiceError,
    LLMTimeoutError,
)
from router.application.decision.output_formatter import OutputFormatter
from router.application.decision.rule_engine_v2 import RuleEngineV2
from router.application.retrieval.retrieval_engine import RetrievalEngine
from router.application.signals.signal_engine import SignalEngine
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.decision_models import (
    ActionParameters,
    CalibratedDecision,
    ConfidenceBreakdown,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    DecisionMetadata,
    DecisionResult,
    LatencyBreakdown,
    VerificationStatus,
    build_action_params,
)
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.signal import SignalBundle
from router.domain.ports.decision_ports import (
    IConfidenceEngine,
    IDecisionFactory,
    IDecisionLogger,
    IDecisionOrchestrator,
    IDecisionValidator,
    ILLMInterface,
    IOutputFormatter,
    IRuleEngineV2,
)
from router.domain.ports.signal_ports import IDecisionEngine
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction

logger = get_logger(__name__)

_MODEL_VERSION = "llm-router-v2.4.1"
_LLM_TIMEOUT_MS = 250.0


class DecisionEngineV2(IDecisionEngine):
    """Full 12-Stage Decision Intelligence Pipeline.

    Implements the IDecisionEngine port for backward compatibility with the
    routing gateway, returning the 5-tuple output contract:
      (action, message_type, reason, confidence, evidence_ids)

    All Phase 7 sub-components are injected via constructor, enabling
    full testability via mock injection.

    Args:
        signal_engine: Signal computation engine.
        retrieval_engine: Evidence retrieval engine.
        decision_factory: DecisionContext builder.
        rule_engine: Deterministic rule catalog.
        orchestrator: LLM frame constructor.
        llm_interface: Structured LLM reasoning service.
        confidence_engine: Confidence calibration engine.
        validator: 5-pass output validator.
        decision_logger: Async audit logger.
        output_formatter: 5-tuple output adapter.
    """

    def __init__(
        self,
        signal_engine: Optional[SignalEngine] = None,
        retrieval_engine: Optional[RetrievalEngine] = None,
        decision_factory: Optional[IDecisionFactory] = None,
        rule_engine: Optional[IRuleEngineV2] = None,
        orchestrator: Optional[IDecisionOrchestrator] = None,
        llm_interface: Optional[ILLMInterface] = None,
        confidence_engine: Optional[IConfidenceEngine] = None,
        validator: Optional[IDecisionValidator] = None,
        decision_logger: Optional[IDecisionLogger] = None,
        output_formatter: Optional[IOutputFormatter] = None,
    ) -> None:
        """Initialize DecisionEngineV2 with all pipeline components."""
        self._signal_engine = signal_engine or SignalEngine()
        self._retrieval_engine = retrieval_engine or RetrievalEngine()
        self._factory = decision_factory or DecisionFactory()
        self._rule_engine = rule_engine or RuleEngineV2()
        self._orchestrator = orchestrator or DecisionOrchestrator()
        self._llm_interface = llm_interface or LLMInterface()
        self._confidence_engine = confidence_engine or ConfidenceEngine()
        self._validator = validator or DecisionValidator()
        self._logger = decision_logger or DecisionLogger(async_logging=False)
        self._formatter = output_formatter or OutputFormatter()

        logger.info("DecisionEngineV2 initialized with all 12-stage pipeline components.")

    def evaluate_routing(
        self, context: MessageContext
    ) -> Tuple[NotificationAction, MessageType, str, float, List[str]]:
        """Execute the full 12-stage Decision Intelligence Pipeline.

        Returns (action, message_type, reason, calibrated_confidence, evidence_ids).

        Args:
            context: Enriched MessageContext from upstream layers.

        Returns:
            5-tuple matching IDecisionEngine contract.
        """
        pipeline_start = time.perf_counter()
        message_id = context.message_id or context.core_message.message_id or "UNKNOWN"
        decision_id = str(uuid.uuid4())

        logger.info(
            "DecisionEngineV2: pipeline start",
            message_id=message_id,
            decision_id=decision_id,
        )

        # ----------------------------------------------------------------
        # Stage 1-2: Signal Bundle (SignalEngine)
        # ----------------------------------------------------------------
        t_signal_start = time.perf_counter()
        try:
            signal_bundle: SignalBundle = self._signal_engine.compute_signals(context)
        except Exception as exc:
            logger.error("Stage 2 signal computation failed", error=str(exc), message_id=message_id)
            signal_bundle = self._build_empty_signal_bundle(context)
        t_signal_ms = (time.perf_counter() - t_signal_start) * 1000.0

        # ----------------------------------------------------------------
        # Stage 3: Evidence Bundle (RetrievalEngine)
        # ----------------------------------------------------------------
        t_retrieval_start = time.perf_counter()
        try:
            evidence_bundle: EvidenceBundle = self._retrieval_engine.retrieve_evidence(context)
        except Exception as exc:
            logger.error("Stage 3 retrieval failed; using empty bundle", error=str(exc), message_id=message_id)
            evidence_bundle = self._build_empty_evidence_bundle(context)
        t_retrieval_ms = (time.perf_counter() - t_retrieval_start) * 1000.0

        # ----------------------------------------------------------------
        # Stage 4: Decision Preprocessing → DecisionContext
        # ----------------------------------------------------------------
        t_preprocess_start = time.perf_counter()
        try:
            decision_context: DecisionContext = self._factory.build_context(
                message_context=context,
                signal_bundle=signal_bundle,
                evidence_bundle=evidence_bundle,
            )
        except Exception as exc:
            logger.error("Stage 4 DecisionContext build failed", error=str(exc), message_id=message_id)
            return self._emergency_fallback(context, decision_id, str(exc))
        t_preprocess_ms = (time.perf_counter() - t_preprocess_start) * 1000.0

        # ----------------------------------------------------------------
        # Stage 5: Rule Engine Evaluation (Branching Point)
        # ----------------------------------------------------------------
        t_rule_start = time.perf_counter()
        rule_result = self._rule_engine.evaluate(decision_context)
        t_rule_ms = (time.perf_counter() - t_rule_start) * 1000.0

        reasoning_output = None
        llm_latency_ms = 0.0
        decision_path = "FAST_PATH" if (rule_result.rule_fired and rule_result.bypass_llm) else "STANDARD_PATH"

        if not (rule_result.rule_fired and rule_result.bypass_llm):
            # ----------------------------------------------------------------
            # Stage 6: Orchestrator Context Construction
            # ----------------------------------------------------------------
            try:
                reasoner_frame = self._orchestrator.prepare_reasoner_frame(decision_context)
            except Exception as exc:
                logger.error("Stage 6 orchestrator failed", error=str(exc), message_id=message_id)
                reasoner_frame = None

            # ----------------------------------------------------------------
            # Stage 7: LLM Reasoner Execution
            # ----------------------------------------------------------------
            if reasoner_frame is not None:
                t_llm_start = time.perf_counter()
                try:
                    reasoning_output = self._llm_interface.reason(reasoner_frame)
                    llm_latency_ms = reasoning_output.llm_latency_ms
                except (LLMTimeoutError, LLMServiceError) as exc:
                    logger.warning(
                        "Stage 7 LLM failure; switching to FALLBACK_PATH",
                        error=str(exc),
                        message_id=message_id,
                    )
                    decision_path = "FALLBACK_PATH"
                    reasoning_output = None
                    llm_latency_ms = (time.perf_counter() - t_llm_start) * 1000.0

            # ----------------------------------------------------------------
            # Stage 8: Decision Verification (consistency checks on LLM output)
            # ----------------------------------------------------------------
            if reasoning_output is not None:
                reasoning_output = self._verify_reasoning_output(reasoning_output, decision_context)

        # ----------------------------------------------------------------
        # Stage 9: Confidence Calibration
        # ----------------------------------------------------------------
        t_conf_start = time.perf_counter()
        try:
            calibrated = self._confidence_engine.calibrate(
                rule_result=rule_result if rule_result.rule_fired else None,
                reasoning_output=reasoning_output,
                context=decision_context,
            )
        except Exception as exc:
            logger.error("Stage 9 confidence calibration failed", error=str(exc), message_id=message_id)
            calibrated = self._fallback_calibrated_decision(decision_context)
            decision_path = "FALLBACK_PATH"
        t_conf_ms = (time.perf_counter() - t_conf_start) * 1000.0

        # ----------------------------------------------------------------
        # Stage 10: Evidence Verification (grounding check)
        # handled within ConfidenceEngine and DecisionValidator
        # ----------------------------------------------------------------

        # ----------------------------------------------------------------
        # Stage 11: Output Validator
        # ----------------------------------------------------------------
        t_val_start = time.perf_counter()
        validation_result = self._validator.validate(calibrated, decision_context)
        t_val_ms = (time.perf_counter() - t_val_start) * 1000.0

        # Apply fallback if validation failed
        final_action = calibrated.action
        final_category = calibrated.category
        fallback_applied = not validation_result.is_valid
        fallback_reason = None

        if not validation_result.is_valid and validation_result.suggested_fallback_action:
            final_action = validation_result.suggested_fallback_action
            fallback_applied = True
            fallback_reason = " | ".join(validation_result.validation_errors[:3])
            logger.warning(
                "Stage 11 validation failed; applying fallback",
                fallback_action=final_action,
                errors=fallback_reason,
                message_id=message_id,
            )

        # Global low-confidence fallback (decision_flow.md §4.2)
        if calibrated.calibrated_confidence < 0.45 and decision_path == "FALLBACK_PATH":
            final_action = (
                DecisionAction.DELIVER_SILENT
                if signal_bundle.personal_sender_known
                else DecisionAction.SUMMARIZE_LATER
            )
            fallback_applied = True
            fallback_reason = fallback_reason or "LOW_CONFIDENCE_RECOVERY"

        # ----------------------------------------------------------------
        # Stage 12: Assemble Final DecisionResult
        # ----------------------------------------------------------------
        total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0
        t_preprocess_total = t_preprocess_ms + t_signal_ms + t_retrieval_ms

        latency_breakdown = LatencyBreakdown(
            preprocessing_ms=round(t_preprocess_total, 2),
            rule_engine_ms=round(t_rule_ms, 2),
            llm_reasoner_ms=round(llm_latency_ms, 2),
            confidence_calc_ms=round(t_conf_ms, 2),
            validation_ms=round(t_val_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
        )

        verification_status = VerificationStatus(
            schema_valid=validation_result.is_valid or not any(
                "SCHEMA" in e for e in validation_result.validation_errors
            ),
            grounding_verified=not calibrated.grounding_warning,
            consistency_verified=not any(
                "REASONING_INCONSISTENCY" in e for e in validation_result.validation_errors
            ),
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            grounding_warning=calibrated.grounding_warning,
        )

        metadata = DecisionMetadata(
            execution_id=decision_id,
            model_version=_MODEL_VERSION,
            latency_breakdown=latency_breakdown,
            confidence_breakdown=calibrated.confidence_breakdown,
            verification_status=verification_status,
            decision_path=decision_path,
        )

        action_params = build_action_params(final_action)
        reasoning_summary = calibrated.reasoning_summary
        if fallback_applied and fallback_reason:
            reasoning_summary = (
                f"System applied safe default due to output validation correction."
                if "SCHEMA" in (fallback_reason or "")
                else calibrated.reasoning_summary
            )

        decision_result = DecisionResult(
            decision_id=decision_id,
            context_id=decision_context.context_id,
            action=final_action,
            urgency_score=calibrated.urgency_score,
            importance_score=calibrated.importance_score,
            category=final_category,
            reasoning_summary=reasoning_summary[:250],
            triggered_rule_id=calibrated.triggered_rule_id,
            bypassed_llm=calibrated.bypassed_llm,
            action_params=action_params,
            metadata=metadata,
            evidence_ids=calibrated.evidence_ids or [],
        )

        # Add audit hash
        audit_hash = decision_result.compute_audit_hash()
        # Re-create with audit_hash (frozen dataclass workaround via object.__setattr__ is not
        # allowed on frozen; we use metadata directly).
        metadata_with_hash = DecisionMetadata(
            execution_id=metadata.execution_id,
            model_version=metadata.model_version,
            latency_breakdown=metadata.latency_breakdown,
            confidence_breakdown=metadata.confidence_breakdown,
            verification_status=metadata.verification_status,
            audit_hash=audit_hash,
            decision_path=metadata.decision_path,
        )
        decision_result = DecisionResult(
            decision_id=decision_result.decision_id,
            context_id=decision_result.context_id,
            action=decision_result.action,
            urgency_score=decision_result.urgency_score,
            importance_score=decision_result.importance_score,
            category=decision_result.category,
            reasoning_summary=decision_result.reasoning_summary,
            triggered_rule_id=decision_result.triggered_rule_id,
            bypassed_llm=decision_result.bypassed_llm,
            action_params=decision_result.action_params,
            metadata=metadata_with_hash,
            evidence_ids=decision_result.evidence_ids,
        )

        # Stage 12b: Async Audit Logging
        try:
            self._logger.log_decision(decision_result, decision_context)
        except Exception as exc:
            logger.error("Audit logging dispatch error", error=str(exc))

        logger.info(
            "DecisionEngineV2: pipeline complete",
            decision_id=decision_id,
            action=final_action,
            confidence=round(calibrated.calibrated_confidence, 3),
            total_latency_ms=round(total_latency_ms, 2),
            decision_path=decision_path,
        )

        # Stage 12c: Format and return 5-tuple
        return self._formatter.format(decision_result)

    # ------------------------------------------------------------------
    # Stage 8: Reasoning output verification
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_reasoning_output(reasoning_output, context: DecisionContext):
        """Stage 8: Verify logical consistency of LLM output.

        Applies auto-corrections per decision_flow.md Stage 8:
        - DELIVER_IMMEDIATELY requires urgency >= 0.60; else downgrade to DELIVER_SILENT.
        - TRIGGER_EMERGENCY_OVERRIDE requires urgency >= 0.80; else downgrade.

        Args:
            reasoning_output: Raw ReasoningOutput from LLMInterface.
            context: DecisionContext for urgency cross-reference.

        Returns:
            Potentially corrected ReasoningOutput.
        """
        from router.domain.entities.decision_models import ReasoningOutput

        action = reasoning_output.proposed_action
        urgency = reasoning_output.urgency_rating

        corrected_action = action
        if action == DecisionAction.DELIVER_IMMEDIATELY and urgency < 0.60:
            corrected_action = DecisionAction.DELIVER_SILENT
            logger.info(
                "Stage 8: auto-corrected DELIVER_IMMEDIATELY to DELIVER_SILENT (urgency too low)",
                urgency=urgency,
            )
        elif action == DecisionAction.TRIGGER_EMERGENCY_OVERRIDE and urgency < 0.80:
            corrected_action = DecisionAction.DELIVER_IMMEDIATELY
            logger.info(
                "Stage 8: auto-corrected TRIGGER_EMERGENCY_OVERRIDE (urgency too low)",
                urgency=urgency,
            )

        if corrected_action == action:
            return reasoning_output

        return ReasoningOutput(
            proposed_action=corrected_action,
            urgency_rating=reasoning_output.urgency_rating,
            importance_rating=reasoning_output.importance_rating,
            reasoning_summary=reasoning_output.reasoning_summary,
            key_factors=reasoning_output.key_factors,
            raw_confidence=reasoning_output.raw_confidence,
            proposed_category=reasoning_output.proposed_category,
            evidence_ids_referenced=reasoning_output.evidence_ids_referenced,
            llm_latency_ms=reasoning_output.llm_latency_ms,
        )

    # ------------------------------------------------------------------
    # Fallback builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_empty_signal_bundle(context: MessageContext) -> SignalBundle:
        """Build a minimal default SignalBundle for degraded signal scenarios."""
        from router.application.signals.signal_engine import SignalEngine
        try:
            return SignalEngine().compute_signals(context)
        except Exception:
            from router.application.signals.signal_factory import SignalFactory
            return SignalFactory.build_bundle(
                message_id=context.message_id or "UNKNOWN",
                all_signals={},
                latency_ms=0.0,
                global_confidence=0.10,
                global_completeness=0.10,
            )

    @staticmethod
    def _build_empty_evidence_bundle(context: MessageContext) -> EvidenceBundle:
        """Build an empty EvidenceBundle for degraded retrieval scenarios."""
        return EvidenceBundle(
            query_message_id=context.message_id or "UNKNOWN",
            user_id=context.user_id or "UNKNOWN",
            retrieval_confidence=0.0,
            evidence_count=0,
            primary_reason="RETRIEVAL_FAILURE",
        )

    @staticmethod
    def _fallback_calibrated_decision(context: DecisionContext) -> CalibratedDecision:
        """Build a minimal CalibratedDecision for system recovery."""
        action = (
            DecisionAction.DELIVER_SILENT
            if context.signal_bundle.personal_sender_known
            else DecisionAction.SUMMARIZE_LATER
        )
        breakdown = ConfidenceBreakdown(
            raw_llm_confidence=0.50,
            signal_agreement_factor=0.0,
            evidence_relevance_factor=0.0,
            history_adjustment_factor=0.0,
            calibrated_confidence=0.50,
        )
        return CalibratedDecision(
            action=action,
            category=DecisionCategory.PERSONAL_CASUAL,
            urgency_score=0.50,
            importance_score=0.50,
            reasoning_summary="System applied safe default due to calibration error.",
            key_factors=["FALLBACK_PATH"],
            evidence_ids=[],
            calibrated_confidence=0.50,
            confidence_breakdown=breakdown,
            bypassed_llm=False,
            triggered_rule_id=None,
        )

    def _emergency_fallback(
        self,
        context: MessageContext,
        decision_id: str,
        error: str,
    ) -> Tuple[NotificationAction, MessageType, str, float, List[str]]:
        """Return a safe emergency fallback 5-tuple on critical pipeline failure.

        Args:
            context: Original MessageContext.
            decision_id: Generated decision UUID.
            error: Error description.

        Returns:
            Safe 5-tuple for notification delivery.
        """
        logger.error(
            "DecisionEngineV2: emergency fallback triggered",
            decision_id=decision_id,
            error=error,
        )
        return (
            NotificationAction.NOTIFY,
            MessageType.UNKNOWN,
            "Emergency fallback: routing decision could not be computed safely.",
            0.50,
            ["none"],
        )
