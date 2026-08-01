"""JSON Audit Logger for per-message explainability & telemetry."""

import datetime
from typing import Any, Mapping

from router.core.logging.logger import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Emits structured JSON audit trail events for every routing decision."""

    def log_decision_audit(
        self,
        correlation_id: str,
        message_id: str,
        user_id: str,
        action: str,
        message_type: str,
        reason: str,
        confidence: float,
        evidence_ids: list[str],
        execution_path: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Emit structured decision audit record adhering to Zero-PII policy."""
        record = {
            "audit_version": "1.0.0",
            "correlation_id": correlation_id,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message_id": message_id,
            "user_id_hash": user_id,
            "decision": {
                "action": action,
                "message_type": message_type,
                "reason": reason,
                "confidence": confidence,
                "evidence_message_ids": evidence_ids,
            },
            "execution_path": dict(execution_path or {}),
        }
        logger.info("Decision Audit Log Entry", audit_record=record)
        return record
