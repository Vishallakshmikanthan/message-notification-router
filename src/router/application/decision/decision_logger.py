"""DecisionLogger — structured async audit trace and telemetry for DecisionResult.

Records complete decision audit traces including:
- Final routing action and confidence breakdown.
- Feature snapshots (signal scores).
- Latency breakdowns per pipeline stage.
- SHA-256 audit hash for tamper-proof compliance logging.

Spec: decision_engine.md §1 Component Breakdown — DecisionLogger.
      decision_validation.md §3.5 Observability & Auditability.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    DecisionContext,
    DecisionResult,
)
from router.domain.ports.decision_ports import IDecisionLogger

logger = get_logger(__name__)


class DecisionLogger(IDecisionLogger):
    """Async audit logger for Decision Intelligence Layer telemetry.

    Dispatch strategy:
    - Decision audit traces are dispatched asynchronously in a daemon thread.
    - This keeps inline latency < 1ms for the main decision pipeline.
    - Async errors are caught and logged without propagation.

    Pluggable sink:
    - By default, audit traces are written to the structured logger.
    - Inject a custom ``audit_sink`` callable to route to BigQuery, ClickHouse,
      OpenTelemetry, or any structured telemetry backend.

    Args:
        audit_sink: Optional callable(audit_record: dict) -> None.
                    Called asynchronously with the full audit payload.
        async_logging: If True (default), dispatch in a daemon thread.
                       Set to False for synchronous testing.
    """

    def __init__(
        self,
        audit_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        async_logging: bool = True,
    ) -> None:
        """Initialize DecisionLogger with optional audit sink.

        Args:
            audit_sink: External telemetry sink callable.
            async_logging: Whether to dispatch asynchronously.
        """
        self._audit_sink = audit_sink
        self._async_logging = async_logging
        logger.info(
            "DecisionLogger initialized",
            async_logging=async_logging,
            has_audit_sink=audit_sink is not None,
        )

    def log_decision(
        self,
        decision_result: DecisionResult,
        context: DecisionContext,
    ) -> None:
        """Asynchronously record a structured decision audit trace.

        The audit record includes:
        - execution_id and context_id for distributed trace correlation.
        - Final action, category, confidence, and reasoning summary.
        - Full latency breakdown per pipeline stage.
        - Signal feature snapshot (top scores).
        - SHA-256 audit hash for tamper-proof logging.

        Args:
            decision_result: The validated final DecisionResult.
            context: The DecisionContext used to generate the result.
        """
        if self._async_logging:
            thread = threading.Thread(
                target=self._log_synchronously,
                args=(decision_result, context),
                daemon=True,
            )
            thread.start()
        else:
            self._log_synchronously(decision_result, context)

    def _log_synchronously(
        self,
        decision_result: DecisionResult,
        context: DecisionContext,
    ) -> None:
        """Internal synchronous log execution.

        Args:
            decision_result: DecisionResult payload.
            context: Source DecisionContext.
        """
        try:
            audit_record = self._build_audit_record(decision_result, context)

            # Write to structured logger (primary)
            logger.info(
                "DECISION_AUDIT",
                execution_id=audit_record["execution_id"],
                context_id=audit_record["context_id"],
                action=audit_record["action"],
                category=audit_record["category"],
                calibrated_confidence=audit_record["calibrated_confidence"],
                bypassed_llm=audit_record["bypassed_llm"],
                triggered_rule_id=audit_record["triggered_rule_id"],
                total_latency_ms=audit_record["latency"]["total_latency_ms"],
                fallback_applied=audit_record["verification"]["fallback_applied"],
                audit_hash=audit_record["audit_hash"],
            )

            # Dispatch to external sink if configured
            if self._audit_sink is not None:
                self._audit_sink(audit_record)

        except Exception as exc:
            # Audit logging failures MUST NOT propagate to the decision pipeline.
            logger.error(
                "DecisionLogger async logging error",
                error=str(exc),
                execution_id=getattr(decision_result, "decision_id", "UNKNOWN"),
            )

    @staticmethod
    def _build_audit_record(
        decision_result: DecisionResult,
        context: DecisionContext,
    ) -> Dict[str, Any]:
        """Build the complete structured audit record.

        Args:
            decision_result: DecisionResult payload.
            context: Source DecisionContext.

        Returns:
            Dict with all audit fields.
        """
        sb = context.signal_bundle
        meta = decision_result.metadata
        cb = meta.confidence_breakdown
        lb = meta.latency_breakdown
        vs = meta.verification_status

        # Feature snapshot (top signal scores)
        signal_snapshot = {
            "urgency_score": sb.urgency_score,
            "spam_score": sb.risk.spam.score,
            "scam_score": sb.risk.scam.score,
            "trust_score": sb.trust.relationship_score.score,
            "relationship_closeness": sb.trust.known_contact_score.score,
            "is_quiet_hours": sb.is_quiet_hours,
            "notification_fatigue": sb.notification_fatigue_score,
            "historical_open_rate": sb.history.historical_open_rate.score,
        }

        return {
            # Correlation IDs
            "execution_id": decision_result.decision_id,
            "context_id": decision_result.context_id,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            # Decision outcome
            "action": str(decision_result.action),
            "category": str(decision_result.category),
            "urgency_score": decision_result.urgency_score,
            "importance_score": decision_result.importance_score,
            "reasoning_summary": decision_result.reasoning_summary,
            "triggered_rule_id": decision_result.triggered_rule_id,
            "bypassed_llm": decision_result.bypassed_llm,
            "evidence_ids": decision_result.evidence_ids,
            # Confidence breakdown
            "calibrated_confidence": cb.calibrated_confidence,
            "confidence_breakdown": {
                "raw_llm_confidence": cb.raw_llm_confidence,
                "signal_agreement_factor": cb.signal_agreement_factor,
                "evidence_relevance_factor": cb.evidence_relevance_factor,
                "history_adjustment_factor": cb.history_adjustment_factor,
                "calibrated_confidence": cb.calibrated_confidence,
            },
            # Latency breakdown
            "latency": {
                "preprocessing_ms": lb.preprocessing_ms,
                "rule_engine_ms": lb.rule_engine_ms,
                "llm_reasoner_ms": lb.llm_reasoner_ms,
                "confidence_calc_ms": lb.confidence_calc_ms,
                "validation_ms": lb.validation_ms,
                "total_latency_ms": lb.total_latency_ms,
            },
            # Verification status
            "verification": {
                "schema_valid": vs.schema_valid,
                "grounding_verified": vs.grounding_verified,
                "consistency_verified": vs.consistency_verified,
                "fallback_applied": vs.fallback_applied,
                "fallback_reason": vs.fallback_reason,
                "grounding_warning": vs.grounding_warning,
            },
            # Signal feature snapshot
            "signal_snapshot": signal_snapshot,
            # Model info
            "model_version": meta.model_version,
            "decision_path": meta.decision_path,
            # Tamper-proof audit hash
            "audit_hash": decision_result.audit_hash,
        }
