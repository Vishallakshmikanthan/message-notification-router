"""Unit tests for Phase 9 Evaluation Framework & Observability."""

import pytest
from eval.metrics_engine import MetricsEngine
from eval.output_validator import OutputCSVValidator
from eval.regression_tester import RegressionTester
from router.infrastructure.observability.telemetry import TelemetryCollector
from router.infrastructure.observability.trace_manager import TraceManager


def test_metrics_engine():
    me = MetricsEngine()
    y_true = ["NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "DO_NOT_DISTURB"]
    y_pred = ["NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "SUMMARIZE_IN_BATCH"]
    confs = [0.95, 0.80, 0.60]

    res = me.compute_all_metrics(y_true, y_pred, confs)
    assert res.accuracy > 0.0
    assert 0.0 <= res.macro_f1 <= 1.0
    assert res.total_penalty_score >= 0


def test_regression_tester():
    rt = RegressionTester(min_macro_f1=0.90, max_ece=0.10, max_penalty_per_1000=100.0)
    me = MetricsEngine()
    actions = ["NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "SUMMARIZE_IN_BATCH", "DO_NOT_DISTURB"]
    y_true = actions * 5
    y_pred = actions * 5
    confs = [1.0] * 20
    metrics = me.compute_all_metrics(y_true, y_pred, confs)

    res = rt.assert_gate_compliance(metrics, p95_latency_ms=500.0)
    assert res["passed"]


def test_telemetry_collector():
    tc = TelemetryCollector.get_instance()
    tc.record_request(latency_ms=150.0, tier=1, tokens_used=400, cache_hit=True)
    summary = tc.get_summary()
    assert summary["tokens_used_total"] >= 400


def test_trace_manager():
    tm = TraceManager(correlation_id="corr-test-123")
    span1 = tm.start_span("span_1")
    span2 = tm.start_span("span_2")
    tm.end_span(span2)
    tm.end_span(span1)

    summary = tm.export_trace_summary()
    assert summary["correlation_id"] == "corr-test-123"
    assert len(summary["spans"]) == 2
