"""DecisionEngine implementation implementing IDecisionEngine contract."""

from router.application.decision.confidence_calibrator import ConfidenceCalibrator
from router.application.rules.rule_engine import RuleEngine
from router.application.signals.signal_engine import SignalEngine
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.ports.signal_ports import IDecisionEngine, IRuleEngine, ISignalEngine
from router.domain.value_objects.message_type import MessageType
from router.domain.value_objects.notification_action import NotificationAction

logger = get_logger(__name__)


class DecisionEngine(IDecisionEngine):
    """Main Routing Decision Engine combining Signal Engine, Hard Filter Rules, and LLM reasoning."""

    def __init__(
        self,
        signal_engine: ISignalEngine | None = None,
        rule_engine: IRuleEngine | None = None,
        calibrator: ConfidenceCalibrator | None = None,
    ) -> None:
        """Initialize DecisionEngine components."""
        self.signal_engine = signal_engine or SignalEngine()
        self.rule_engine = rule_engine or RuleEngine()
        self.calibrator = calibrator or ConfidenceCalibrator()

    def evaluate_routing(
        self, context: MessageContext
    ) -> tuple[NotificationAction, MessageType, str, float, list[str]]:
        """Evaluate routing decision for given message context.

        Returns (action, message_type, reason, calibrated_confidence, evidence_ids).
        """
        logger.info("Evaluating routing for message", message_id=context.message_id)

        # Step 1: Compute Signal Bundle
        signals = self.signal_engine.compute_signals(context)

        # Step 2: Evaluate Rule-Based Hard Filter
        hard_filter_res = self.rule_engine.evaluate(signals, context)
        if hard_filter_res:
            action, msg_type, reason, raw_conf = hard_filter_res
            calibrated_conf = self.calibrator.calibrate(raw_conf, signals, context, is_hard_filter=True)
            return (action, msg_type, reason, calibrated_conf, ["none"])

        # Step 3: Default LLM reasoning pass fallback stub
        action = NotificationAction.NOTIFY
        msg_type = MessageType.PERSONAL
        reason = "Personal direct communication from contact requiring user attention."
        raw_conf = 0.85
        evidence_ids = ["none"]

        calibrated_conf = self.calibrator.calibrate(raw_conf, signals, context, is_hard_filter=False)
        return (action, msg_type, reason, calibrated_conf, evidence_ids)
