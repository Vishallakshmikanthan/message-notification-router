"""Distributed Tracing Architecture (OpenTelemetry Span Management).

Implements Distributed Tracing Architecture from observability.md §2:
- Assigns unique correlation_id (UUIDv4) to every notification request.
- Manages span lifecycle for micro-agent execution steps.
- Tracks parent/child span hierarchy.

Spec: observability.md §2 (OpenTelemetry Span Hierarchy).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Represents a single distributed trace span."""

    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "OK"

    def finish(self, status: str = "OK") -> None:
        """Mark span as complete."""
        self.end_time = time.time()
        self.status = status

    @property
    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000.0


class TraceManager:
    """Manages OpenTelemetry spans and correlation ID context."""

    def __init__(self, correlation_id: str | None = None) -> None:
        """Initialize TraceManager for a request context."""
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.spans: list[Span] = []
        self._active_spans: list[Span] = []
        logger.debug("TraceManager initialized", extra={"correlation_id": self.correlation_id})

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Span:
        """Start a new child span."""
        parent_id = self._active_spans[-1].span_id if self._active_spans else None
        span = Span(
            name=name,
            trace_id=self.correlation_id,
            parent_span_id=parent_id,
            attributes=attributes or {},
        )
        self.spans.append(span)
        self._active_spans.append(span)
        logger.debug("Span started", extra={"span_name": name, "correlation_id": self.correlation_id})
        return span

    def end_span(self, span: Span, status: str = "OK") -> None:
        """End an active span."""
        span.finish(status)
        if span in self._active_spans:
            self._active_spans.remove(span)
        logger.debug("Span ended", extra={"span_name": span.name, "duration_ms": round(span.duration_ms, 2)})

    def export_trace_summary(self) -> dict[str, Any]:
        """Export summary of all spans in trace."""
        return {
            "correlation_id": self.correlation_id,
            "span_count": len(self.spans),
            "spans": [
                {
                    "name": s.name,
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "duration_ms": round(s.duration_ms, 2),
                    "status": s.status,
                    "attributes": s.attributes,
                }
                for s in self.spans
            ],
        }
