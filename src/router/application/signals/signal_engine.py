"""SignalEngine implementation coordinating the full 12-stage signal computation DAG specifications."""

import time

from router.application.signals.behaviour_engine import BehaviourEngine
from router.application.signals.personalization_engine import PersonalizationEngine
from router.application.signals.risk_engine import RiskEngine
from router.application.signals.signal_aggregator import SignalAggregator
from router.application.signals.signal_factory import SignalFactory
from router.application.signals.signal_normalizer import SignalNormalizer
from router.application.signals.signal_registry import SignalRegistry
from router.application.signals.signal_validator import SignalValidator
from router.application.signals.trust_engine import TrustEngine
from router.application.signals.urgency_engine import UrgencyEngine
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalBundle, SignalValue
from router.domain.ports.signal_ports import ISignalEngine

logger = get_logger(__name__)


class SignalEngine(ISignalEngine):
    """Deterministic Signal Computation Engine transforming MessageContext into an immutable SignalBundle."""

    def __init__(self) -> None:
        """Initialize validator, engines, normalizer, and calculator registry."""
        self.validator = SignalValidator()
        self.normalizer = SignalNormalizer()
        self.registry = SignalRegistry()

        self.behaviour_engine = BehaviourEngine()
        self.risk_engine = RiskEngine()
        self.trust_engine = TrustEngine()
        self.urgency_engine = UrgencyEngine()
        self.personalization_engine = PersonalizationEngine()

        self._register_default_calculators()

    def _register_default_calculators(self) -> None:
        """Register all engine sub-calculators in central registry."""
        for engine in [
            self.behaviour_engine,
            self.risk_engine,
            self.trust_engine,
            self.urgency_engine,
            self.personalization_engine,
        ]:
            for calc in getattr(engine, "calculators", []):
                self.registry.register(calc)

    def compute_signals(self, context: MessageContext) -> SignalBundle:
        """Execute 12-stage analytical pipeline and return single frozen SignalBundle."""
        start_time = time.perf_counter()
        message_id = context.core_message.message_id or context.message_id or "UNKNOWN_MSG"

        logger.info("Executing SignalEngine computation pipeline", message_id=message_id)

        # Stage 1: Context Validation & Quality Pre-Check
        pre_check_completeness = self.validator.validate_pre_check(context)

        # Short-circuit protocol for corrupted contexts (Q_comp < 0.20)
        if pre_check_completeness < 0.20:
            logger.warning(
                "Short-circuiting signal computation due to low completeness",
                message_id=message_id,
                completeness=pre_check_completeness,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return SignalFactory.build_bundle(
                message_id=message_id,
                all_signals={},
                latency_ms=elapsed_ms,
                global_confidence=0.10,
                global_completeness=pre_check_completeness,
            )

        # Stages 2-10: Parallel Category Execution
        raw_signals: dict[str, SignalValue] = {}
        raw_signals.update(self.behaviour_engine.calculate_all(context))
        raw_signals.update(self.risk_engine.calculate_all(context))
        raw_signals.update(self.trust_engine.calculate_all(context))
        raw_signals.update(self.urgency_engine.calculate_all(context))
        raw_signals.update(self.personalization_engine.calculate_all(context))

        # Stage 11: Normalization & Conflict Resolution
        normalized_signals: dict[str, SignalValue] = {
            k: self.normalizer.normalize_signal(v) for k, v in raw_signals.items()
        }
        resolved_signals = self.normalizer.resolve_conflicts(normalized_signals)

        # Stage 12: Aggregation & Assembly
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        bundle = SignalAggregator.assemble_bundle(
            message_id=message_id,
            signals=resolved_signals,
            latency_ms=elapsed_ms,
            pre_check_completeness=pre_check_completeness,
        )

        self.validator.validate_bundle(bundle)
        logger.info(
            "Completed SignalEngine computation",
            message_id=message_id,
            latency_ms=round(elapsed_ms, 2),
            global_confidence=bundle.metadata.global_confidence,
            global_completeness=bundle.metadata.global_completeness,
        )
        return bundle
