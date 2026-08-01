"""Observability Package Init.

Exports telemetry and tracing utilities:
- TelemetryCollector: Prometheus metrics singleton.
- TraceManager: OpenTelemetry span manager.
"""

from router.infrastructure.observability.telemetry import TelemetryCollector
from router.infrastructure.observability.trace_manager import Span, TraceManager

__all__ = [
    "TelemetryCollector",
    "TraceManager",
    "Span",
]
