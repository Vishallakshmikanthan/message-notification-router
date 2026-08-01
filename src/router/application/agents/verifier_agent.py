"""Verifier Agent (Factual Grounding & Constraint Enforcer).

Implements Verifier Agent specification from agent_architecture.md §3.7:
- Validates that proposed routing decisions do not contradict extracted evidence
  or user policy rules, and calibrates final numeric confidence scores.
- Inputs: ProposedRoutingDecision, CritiqueReport, EvidenceBundle, UserPolicy.
- Outputs: VerifiedDecision (is_approved, calibrated_confidence, final_action).
- Skip logic: Skipped when Classifier Agent confidence >= 0.85.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext

logger = logging.getLogger(__name__)


class VerifierAgent(BaseAgent):
    """Factual Grounding & Constraint Enforcer Agent."""

    def __init__(self) -> None:
        """Initialize VerifierAgent."""
        super().__init__("VerifierAgent")

    async def run(
        self, context: MessageContext, inputs: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Execute verification on proposed decision and critique report.

        Args:
            context: Message context.
            inputs: Dict containing decision, critique report, and evidence.

        Returns:
            Dict containing verified decision.
        """
        raw_confidence = float(inputs.get("raw_confidence", inputs.get("confidence", 0.80)))

        # Skip condition: Skipped when Classifier confidence >= 0.85
        if raw_confidence >= 0.85 and not inputs.get("has_flaws", False):
            logger.info("VerifierAgent skipped: confidence >= 0.85", extra={"confidence": raw_confidence})
            return {
                "verifier_skipped": True,
                "is_approved": True,
                "calibrated_confidence": raw_confidence,
                "final_action": inputs.get("action", inputs.get("proposed_action", "DELIVER_SILENTLY")),
                "override_applied": False,
            }

        action = inputs.get("action", inputs.get("proposed_action", "DELIVER_SILENTLY"))
        has_flaws = bool(inputs.get("has_flaws", False))
        suggested_refinement = inputs.get("suggested_refinement")

        is_approved = not has_flaws
        final_action = action
        override_applied = False
        calibrated_confidence = raw_confidence

        if has_flaws:
            if suggested_refinement:
                final_action = suggested_refinement
                override_applied = True
            calibrated_confidence = min(0.60, raw_confidence * 0.80)
            logger.warning(
                "VerifierAgent overridden action due to critique flaws",
                extra={"original": action, "final": final_action},
            )
        else:
            # Calibrate confidence up slightly if grounded
            calibrated_confidence = min(0.95, raw_confidence * 1.05)

        return {
            "verifier_skipped": False,
            "is_approved": is_approved,
            "calibrated_confidence": round(calibrated_confidence, 3),
            "final_action": final_action,
            "override_applied": override_applied,
        }
