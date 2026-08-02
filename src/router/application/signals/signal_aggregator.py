"""SignalAggregator implementation for assembling individual signal scores into category containers and master bundle."""


from router.application.signals.signal_factory import SignalFactory
from router.core.logging.logger import get_logger
from router.domain.entities.signal import SignalBundle, SignalValue

logger = get_logger(__name__)

# Standard target number of signals across all 11 category blocks
TOTAL_EXPECTED_SIGNALS = 40


class SignalAggregator:
    """Combines individual computed SignalValue objects into category containers and constructs SignalBundle."""

    @classmethod
    def assemble_bundle(
        cls,
        message_id: str,
        signals: dict[str, SignalValue],
        latency_ms: float,
        pre_check_completeness: float,
    ) -> SignalBundle:
        """Calculate global confidence and completeness and return frozen SignalBundle."""
        computed_count = len(signals)

        if computed_count > 0:
            total_conf = sum(sig.confidence for sig in signals.values())
            global_confidence = total_conf / computed_count
        else:
            global_confidence = 0.0

        # Completeness calculation: weighted blend of pre-check schema score & signal coverage fraction
        coverage_fraction = min(1.0, computed_count / float(TOTAL_EXPECTED_SIGNALS))
        global_completeness = max(0.0, min(1.0, 0.5 * pre_check_completeness + 0.5 * coverage_fraction))

        logger.debug(
            "Aggregating signals into SignalBundle",
            message_id=message_id,
            computed_signals=computed_count,
            global_confidence=global_confidence,
            global_completeness=global_completeness,
            latency_ms=latency_ms,
        )

        return SignalFactory.build_bundle(
            message_id=message_id,
            all_signals=signals,
            latency_ms=latency_ms,
            global_confidence=global_confidence,
            global_completeness=global_completeness,
        )
