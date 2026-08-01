"""OutputFormatter — maps DecisionResult to the IDecisionEngine 5-tuple contract.

Provides the backward-compatibility bridge between the Phase 7 Decision Intelligence
Layer (which operates on DecisionResult/DecisionAction/DecisionCategory) and the
existing IDecisionEngine interface (which returns the 5-tuple:
  (NotificationAction, MessageType, str, float, list[str])).

Spec: decision_engine.md §1 Component Breakdown (DecisionEngine output contract).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    DecisionAction,
    DecisionCategory,
    DecisionResult,
)
from router.domain.ports.decision_ports import IOutputFormatter
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction

logger = get_logger(__name__)

# Mapping: DecisionAction -> NotificationAction (legacy enum)
_ACTION_MAP: Dict[DecisionAction, NotificationAction] = {
    DecisionAction.DELIVER_IMMEDIATELY: NotificationAction.NOTIFY,
    DecisionAction.DELIVER_SILENT: NotificationAction.NOTIFY,
    DecisionAction.SUMMARIZE_LATER: NotificationAction.DIGEST,
    DecisionAction.BATCH_DIGEST: NotificationAction.DIGEST,
    DecisionAction.SUPPRESS_SPAM: NotificationAction.MUTE,
    DecisionAction.SUPPRESS_MUTE: NotificationAction.MUTE,
    DecisionAction.TRIGGER_EMERGENCY_OVERRIDE: NotificationAction.NOTIFY,
}

# Mapping: DecisionCategory -> MessageType (legacy enum)
_CATEGORY_MAP: Dict[DecisionCategory, MessageType] = {
    DecisionCategory.PERSONAL_URGENT: MessageType.URGENT,
    DecisionCategory.PERSONAL_CASUAL: MessageType.PERSONAL,
    DecisionCategory.WORK_CRITICAL: MessageType.URGENT,
    DecisionCategory.WORK_ROUTINE: MessageType.PERSONAL,
    DecisionCategory.TRANSACTIONAL: MessageType.PAYMENT,
    DecisionCategory.MARKETING_PROMO: MessageType.PROMOTION,
    DecisionCategory.SAFETY_SECURITY: MessageType.SCAM,
    DecisionCategory.SPAM_VIRAL: MessageType.SPAM,
}


class OutputFormatter(IOutputFormatter):
    """Maps a validated DecisionResult to the legacy IDecisionEngine 5-tuple.

    The 5-tuple contract is:
        (NotificationAction, MessageType, reasoning_summary, confidence, evidence_ids)

    This is the final stage of the Decision Intelligence Layer pipeline and
    serves as the adapter between the new rich DecisionResult model and the
    existing IDecisionEngine port that the routing gateway depends on.
    """

    def format(
        self,
        decision_result: DecisionResult,
    ) -> Tuple[NotificationAction, MessageType, str, float, List[str]]:
        """Map a DecisionResult to the legacy 5-tuple IDecisionEngine output contract.

        Args:
            decision_result: Fully validated and logged DecisionResult.

        Returns:
            5-tuple: (action, message_type, reason, confidence, evidence_ids).
        """
        # Map DecisionAction -> NotificationAction
        action = _ACTION_MAP.get(decision_result.action, NotificationAction.NOTIFY)

        # Map DecisionCategory -> MessageType
        message_type = _CATEGORY_MAP.get(
            decision_result.category, MessageType.PERSONAL
        )

        # Reason: use reasoning_summary (already capped at 250 chars)
        reason = decision_result.reasoning_summary or "Routing decision applied."

        # Confidence: calibrated posterior probability
        confidence = decision_result.metadata.confidence_breakdown.calibrated_confidence

        # Evidence IDs: deduplicated list, filter out placeholder "none" values
        evidence_ids: List[str] = [
            eid
            for eid in decision_result.evidence_ids
            if eid and eid.lower() != "none"
        ]
        if not evidence_ids:
            evidence_ids = ["none"]

        logger.info(
            "OutputFormatter: decision formatted",
            decision_id=decision_result.decision_id,
            action=action,
            message_type=message_type,
            confidence=round(confidence, 3),
            evidence_count=len(evidence_ids),
        )

        return (action, message_type, reason, confidence, evidence_ids)
