"""Critic Agent (Adversarial Evaluator).

Implements Critic Agent specification from agent_architecture.md §3.6:
- Performs adversarial critique on proposed decisions with low confidence (<0.75)
  or conflicting signals, identifying potential flaws or missing user context.
- Inputs: ProposedRoutingDecision, SanitizedMessage, EvidenceBundle.
- Outputs: CritiqueReport (has_flaws, flaw_type, suggested_refinement).
- Skip logic: Skipped when Classifier Agent confidence >= 0.75 and context risk is low.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional

from router.application.agents.base_agent import BaseAgent
from router.domain.entities.context import MessageContext

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Adversarial Evaluator Agent for low-confidence or high-risk decisions."""

    def __init__(self) -> None:
        """Initialize CriticAgent."""
        super().__init__("CriticAgent")

    async def run(
        self, context: MessageContext, inputs: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Execute adversarial critique on proposed decision.

        Args:
            context: Message context.
            inputs: Dict containing proposed decision and evidence.

        Returns:
            Dict containing critique results.
        """
        raw_confidence = float(inputs.get("raw_confidence", inputs.get("confidence", 0.80)))
        has_conflicts = bool(inputs.get("conflicting_signals", False))

        # Check skip condition: Skipped when Classifier confidence >= 0.75 and no conflicts
        if raw_confidence >= 0.75 and not has_conflicts:
            logger.info("CriticAgent skipped: high confidence & low risk", extra={"confidence": raw_confidence})
            return {
                "critic_skipped": True,
                "has_flaws": False,
                "flaw_type": None,
                "suggested_refinement": None,
            }

        # Analyze potential flaws
        flaws: List[str] = []
        proposed_action = inputs.get("action", inputs.get("proposed_action", "DELIVER_SILENTLY"))

        urgency_score = float(inputs.get("urgency_score", 0.5))
        is_quiet_hours = bool(inputs.get("is_quiet_hours", False))
        sender_is_vip = bool(inputs.get("sender_is_vip", False))

        if proposed_action == "NOTIFY_IMMEDIATELY" and urgency_score < 0.60:
            flaws.append("UNCLEAR_URGENCY_CONTEXT")

        if proposed_action == "DO_NOT_DISTURB" and sender_is_vip:
            flaws.append("VIP_MUTED_CONTRADICTION")

        if proposed_action == "NOTIFY_IMMEDIATELY" and is_quiet_hours and not sender_is_vip:
            flaws.append("QUIET_HOURS_VIOLATION")

        has_flaws = len(flaws) > 0
        flaw_type = flaws[0] if has_flaws else None
        suggested_refinement = "DELIVER_SILENTLY" if has_flaws else None

        logger.info(
            "CriticAgent evaluated decision",
            extra={"has_flaws": has_flaws, "flaw_type": flaw_type, "confidence": raw_confidence},
        )

        return {
            "critic_skipped": False,
            "has_flaws": has_flaws,
            "flaw_type": flaw_type,
            "suggested_refinement": suggested_refinement,
            "identified_flaws": flaws,
        }
