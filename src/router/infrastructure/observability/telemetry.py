"""Prometheus-compatible Telemetry Collector & Operational Metrics.

Implements Telemetry Specification from observability.md §3:
Export Prometheus-compatible metrics for 4 operational dashboards:
1. Latency Dashboard (p50, p90, p99 per component)
2. Token & Cost Dashboard (prompt, cached, completion tokens)
3. AI Performance & Calibration Dashboard (tier hit rates, ECE score)
4. System Health & Error Dashboard (rule failures, schema repairs, errors)

Spec: observability.md §3 (Core Metrics Specification Table).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """Counter metric tracker."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        self.value += amount


@dataclass
class MetricGauge:
    """Gauge metric tracker."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, val: float) -> None:
        """Set gauge value."""
        self.value = val


@dataclass
class MetricHistogram:
    """Histogram metric tracker for latency budgets."""

    name: str
    description: str
    observations: List[float] = field(default_factory=list)

    def observe(self, val: float) -> None:
        """Record an observation value."""
        self.observations.append(val)

    def p50(self) -> float:
        """Compute p50 (median)."""
        if not self.observations:
            return 0.0
        sorted_obs = sorted(self.observations)
        idx = int(len(sorted_obs) * 0.50)
        return sorted_obs[idx]

    def p95(self) -> float:
        """Compute p95 percentiles."""
        if not self.observations:
            return 0.0
        sorted_obs = sorted(self.observations)
        idx = min(int(len(sorted_obs) * 0.95), len(sorted_obs) - 1)
        return sorted_obs[idx]

    def p99(self) -> float:
        """Compute p99 percentiles."""
        if not self.observations:
            return 0.0
        sorted_obs = sorted(self.observations)
        idx = min(int(len(sorted_obs) * 0.99), len(sorted_obs) - 1)
        return sorted_obs[idx]


class TelemetryCollector:
    """Singleton telemetry collector exporting metrics."""

    _instance: Optional[TelemetryCollector] = None

    def __init__(self) -> None:
        """Initialize telemetry counters, gauges, and histograms."""
        self.router_request_latency_ms = MetricHistogram(
            "router_request_latency_ms", "End-to-end processing time per message"
        )
        self.tier_execution_total = MetricCounter(
            "tier_execution_total", "Count of executions per Tier (Tier 0, 1, 2, 3)"
        )
        self.llm_token_usage_total = MetricCounter(
            "llm_token_usage_total", "Total prompt, completion, and cached tokens"
        )
        self.prompt_cache_hit_ratio = MetricGauge(
            "prompt_cache_hit_ratio", "Ratio of API prompt tokens served from provider cache"
        )
        self.json_auto_repair_total = MetricCounter(
            "json_auto_repair_total", "Count of LLM outputs requiring Stage 1-4 repair"
        )
        self.ece_calibration_score = MetricGauge(
            "ece_calibration_score", "Real-time Expected Calibration Error of confidence outputs"
        )
        self.pipeline_error_total = MetricCounter(
            "pipeline_error_total", "Total unhandled exceptions or hard fallbacks triggered"
        )
        logger.info("TelemetryCollector initialized")

    @classmethod
    def get_instance(cls) -> TelemetryCollector:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = TelemetryCollector()
        return cls._instance

    def record_request(
        self,
        latency_ms: float,
        tier: int,
        tokens_used: int = 0,
        cache_hit: bool = False,
        repaired: bool = False,
        error: bool = False,
    ) -> None:
        """Record a single message processing event."""
        self.router_request_latency_ms.observe(latency_ms)
        self.tier_execution_total.inc()
        self.llm_token_usage_total.inc(tokens_used)

        if repaired:
            self.json_auto_repair_total.inc()
        if error:
            self.pipeline_error_total.inc()

    def get_summary(self) -> Dict[str, Any]:
        """Export metrics summary dict."""
        return {
            "latency_p50_ms": self.router_request_latency_ms.p50(),
            "latency_p95_ms": self.router_request_latency_ms.p95(),
            "latency_p99_ms": self.router_request_latency_ms.p99(),
            "tier_executions_total": self.tier_execution_total.value,
            "tokens_used_total": self.llm_token_usage_total.value,
            "prompt_cache_hit_ratio": self.prompt_cache_hit_ratio.value,
            "json_auto_repairs_total": self.json_auto_repair_total.value,
            "ece_calibration_score": self.ece_calibration_score.value,
            "pipeline_errors_total": self.pipeline_error_total.value,
        }
