"""Telemetry & Operational Metrics Infrastructure Component."""

import time
from typing import Any, Mapping

from router.core.logging.logger import get_logger

logger = get_logger(__name__)


class TelemetryCollector:
    """Collects and exports OpenTelemetry/Prometheus compatible metrics."""

    def __init__(self) -> None:
        """Initialize metric counters and histograms."""
        self._counters: dict[str, int] = {}

    def increment_counter(self, metric_name: str, value: int = 1) -> None:
        """Increment a metric counter."""
        self._counters[metric_name] = self._counters.get(metric_name, 0) + value

    def record_latency(self, component: str, latency_ms: float) -> None:
        """Record component execution latency in milliseconds."""
        logger.debug("Component execution latency", component=component, latency_ms=latency_ms)

    def get_metrics_summary(self) -> Mapping[str, Any]:
        """Return summary of all collected telemetry metrics."""
        return dict(self._counters)
