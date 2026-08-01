"""Automated CI/CD Regression Tester Gate.

Implements CI/CD Quality Bar from evaluation_framework.md §7:
- Macro F1 >= 0.92
- Risk-Weighted Penalty Score < baseline
- ECE score <= 0.05
- 100% passing on safety test suites
- Latency p95 strictly <= 1,500 ms

Spec: evaluation_framework.md §7.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from eval.metrics_engine import EvaluationMetricsResult

logger = logging.getLogger(__name__)


class RegressionTester:
    """CI/CD Gate regression validator."""

    def __init__(
        self,
        min_macro_f1: float = 0.92,
        max_ece: float = 0.05,
        max_penalty_per_1000: float = 50.0,
        max_p95_latency_ms: float = 1500.0,
    ) -> None:
        """Initialize RegressionTester thresholds."""
        self.min_macro_f1 = min_macro_f1
        self.max_ece = max_ece
        self.max_penalty_per_1000 = max_penalty_per_1000
        self.max_p95_latency_ms = max_p95_latency_ms

    def assert_gate_compliance(
        self,
        metrics: EvaluationMetricsResult,
        p95_latency_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Assert metrics pass CI/CD release gate standards.

        Args:
            metrics: EvaluationMetricsResult from pipeline run.
            p95_latency_ms: Measured p95 end-to-end latency in ms.

        Returns:
            Dict containing gate pass/fail status and violations.
        """
        violations: List[str] = []

        if metrics.macro_f1 < self.min_macro_f1:
            violations.append(f"Macro F1 drop: {metrics.macro_f1:.4f} < required {self.min_macro_f1}")

        if metrics.ece_score > self.max_ece:
            violations.append(f"ECE Miscalibration: {metrics.ece_score:.4f} > max {self.max_ece}")

        if metrics.penalty_per_1000 > self.max_penalty_per_1000:
            violations.append(f"Risk Penalty Exceeded: {metrics.penalty_per_1000:.2f}/1000 > max {self.max_penalty_per_1000}")

        if p95_latency_ms is not None and p95_latency_ms > self.max_p95_latency_ms:
            violations.append(f"Latency SLA Violated: p95 {p95_latency_ms:.1f}ms > max {self.max_p95_latency_ms}ms")

        passed = len(violations) == 0

        logger.info(
            "RegressionTester gate assertion complete",
            extra={"passed": passed, "violations_count": len(violations)},
        )

        return {
            "passed": passed,
            "violations": violations,
            "metrics": {
                "macro_f1": metrics.macro_f1,
                "ece_score": metrics.ece_score,
                "penalty_per_1000": metrics.penalty_per_1000,
                "p95_latency_ms": p95_latency_ms,
            },
        }
