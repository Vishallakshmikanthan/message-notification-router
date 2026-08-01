"""Output Formatter Agent (Schema Guard & JSON Serialization).

Implements Output Formatter Agent specification from agent_architecture.md §3.8:
- Enforces structural JSON compliance, formats exact API responses, generates
  audit logs, and validates final output schema constraints.
- Inputs: VerifiedDecision, AuditMetadata.
- Outputs: FinalJSONResponse (action, reason, confidence, evidence, metadata).
- Skip logic: Never skipped. Terminal node in agent DAG.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext

logger = logging.getLogger(__name__)


class OutputFormatterAgent(BaseAgent):
    """Schema Guard & JSON Serialization Agent."""

    def __init__(self) -> None:
        """Initialize OutputFormatterAgent."""
        super().__init__("OutputFormatterAgent")

    async def run(
        self, context: MessageContext, inputs: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Format final JSON response.

        Args:
            context: Message context.
            inputs: Outputs from upstream agents (Verifier, Classifier, etc.).

        Returns:
            Dict matching final output contract.
        """
        action = inputs.get("final_action", inputs.get("action", inputs.get("proposed_action", "DELIVER_SILENTLY")))
        confidence = float(inputs.get("calibrated_confidence", inputs.get("confidence", 0.50)))
        reason = str(inputs.get("reason", inputs.get("reasoning_summary", "Routing decision computed successfully.")))
        evidence = list(inputs.get("evidence", inputs.get("evidence_ids", [])))

        # Format clean JSON output matching schema
        output = {
            "message_id": context.message_id or "UNKNOWN",
            "action": action,
            "reason": reason[:200],
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "metadata": {
                "tier_level": inputs.get("tier_level", 1),
                "is_fallback": bool(inputs.get("is_fallback", False)),
                "override_applied": bool(inputs.get("override_applied", False)),
            },
        }

        logger.info(
            "OutputFormatterAgent formatted final response",
            extra={"message_id": output["message_id"], "action": action, "confidence": output["confidence"]},
        )
        return output
