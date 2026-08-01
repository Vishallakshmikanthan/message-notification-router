"""SignalEngine implementation implementing ISignalEngine interface contract."""

from router.application.signals.behaviour_engine import BehaviourEngine
from router.application.signals.personalization_engine import PersonalizationEngine
from router.application.signals.risk_engine import RiskEngine
from router.application.signals.signal_validator import SignalValidator
from router.application.signals.trust_engine import TrustEngine
from router.application.signals.urgency_engine import UrgencyEngine
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle
from router.domain.ports.signal_ports import ISignalEngine
from router.domain.value_objects.risk_level import RiskLevel

logger = get_logger(__name__)


class SignalEngine(ISignalEngine):
    """Coordinates parallel signal calculator execution DAG and returns SignalBundle."""

    def __init__(self) -> None:
        """Initialize signal calculators."""
        self.validator = SignalValidator()
        self.behaviour_engine = BehaviourEngine()
        self.trust_engine = TrustEngine()
        self.urgency_engine = UrgencyEngine()
        self.risk_engine = RiskEngine()
        self.personalization_engine = PersonalizationEngine()

    def compute_signals(self, context: MessageContext) -> SignalBundle:
        """Compute all 7 analytical signal modules and return frozen SignalBundle."""
        logger.debug("Computing signals for message context", message_id=context.message_id)

        completeness = self.validator.validate_pre_check(context)
        behaviour_res = self.behaviour_engine.calculate(context)
        trust_res = self.trust_engine.calculate(context)
        urgency_res = self.urgency_engine.calculate(context)
        risk_res = self.risk_engine.calculate(context)
        pers_res = self.personalization_engine.calculate(context)

        risk_val = risk_res.get("risk_level", RiskLevel.NONE)
        assert isinstance(risk_val, RiskLevel)

        bundle = SignalBundle(
            message_id=context.message_id,
            is_quiet_hours=context.is_quiet_hours,
            notification_fatigue_score=float(behaviour_res.get("notification_fatigue_score", 0.0)),
            user_engagement_score=float(behaviour_res.get("user_engagement_score", 0.0)),
            group_relevance_score=float(pers_res.get("group_relevance_score", 0.0)),
            is_admin_message=bool(pers_res.get("is_admin_message", False)),
            group_is_muted_by_user=bool(pers_res.get("group_is_muted_by_user", False)),
            business_trust_score=float(trust_res.get("business_trust_score", 0.0)),
            user_opted_in=bool(pers_res.get("user_opted_in", True)),
            forward_chain_depth=int(risk_res.get("forward_chain_depth", 0)),
            scam_keyword_score=float(risk_res.get("scam_keyword_score", 0.0)),
            unverified_business_flag=bool(risk_res.get("unverified_business_flag", False)),
            risk_level=risk_val,
            urgency_keywords_present=bool(urgency_res.get("urgency_keywords_present", False)),
            personal_sender_known=bool(trust_res.get("personal_sender_known", False)),
            urgency_score=float(urgency_res.get("urgency_score", 0.0)),
            completeness_score=completeness,
        )

        return bundle
