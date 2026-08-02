"""Performance Metrics Tracker — Latency & Token SLA Analyzer.

Implements SLA Budget Tracking from performance.md §1 & §2:
- Sub-20ms Rule Engine Bypass SLA
- Sub-800ms Tier 1 LLM Fast-Path SLA
- Token consumption & cost optimization tracking

Spec: performance.md §1 & §2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceReport:
    """Performance summary analytics report."""

    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    rule_bypass_ratio: float
    tier_1_sla_met: bool
    total_tokens_consumed: int
    estimated_cost_usd: float


class PerformanceMetricsTracker:
    """Tracker for operational performance metrics."""

    def __init__(self, cost_per_1k_tokens: float = 0.00015) -> None:
        """Initialize tracker."""
        self.latencies_ms: list[float] = []
        self.rule_hits = 0
        self.llm_calls = 0
        self.tokens_used = 0
        self.cost_per_1k_tokens = cost_per_1k_tokens

    def record_execution(
        self,
        latency_ms: float,
        bypassed_llm: bool,
        tokens_used: int = 0,
    ) -> None:
        """Record a single execution event."""
        self.latencies_ms.append(latency_ms)
        if bypassed_llm:
            self.rule_hits += 1
        else:
            self.llm_calls += 1
            self.tokens_used += tokens_used

    def generate_report(self) -> PerformanceReport:
        """Compute performance SLA report."""
        if not self.latencies_ms:
            return PerformanceReport(
                p50_latency_ms=0.0,
                p90_latency_ms=0.0,
                p99_latency_ms=0.0,
                avg_latency_ms=0.0,
                rule_bypass_ratio=0.0,
                tier_1_sla_met=True,
                total_tokens_consumed=0,
                estimated_cost_usd=0.0,
            )

        sorted_lat = sorted(self.latencies_ms)
        n = len(sorted_lat)

        p50 = sorted_lat[int(n * 0.50)]
        p90 = sorted_lat[min(int(n * 0.90), n - 1)]
        p99 = sorted_lat[min(int(n * 0.99), n - 1)]
        avg = sum(sorted_lat) / n

        bypass_ratio = self.rule_hits / n
        tier_1_sla = p90 <= 800.0
        cost = (self.tokens_used / 1000.0) * self.cost_per_1k_tokens

        return PerformanceReport(
            p50_latency_ms=round(p50, 2),
            p90_latency_ms=round(p90, 2),
            p99_latency_ms=round(p99, 2),
            avg_latency_ms=round(avg, 2),
            rule_bypass_ratio=round(bypass_ratio, 3),
            tier_1_sla_met=tier_1_sla,
            total_tokens_consumed=self.tokens_used,
            estimated_cost_usd=round(cost, 6),
        )
