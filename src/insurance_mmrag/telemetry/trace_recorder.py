"""OpenTelemetry-style span recorder producing a per-query execution waterfall."""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from insurance_mmrag.schemas import TraceSpan

AttrValue = str | int | float | bool


class SpanHandle:
    """Mutable handle yielded inside a span so callers can attach attributes."""

    def __init__(self, span_id: str) -> None:
        self.span_id = span_id
        self.attributes: dict[str, AttrValue] = {}

    def set(self, key: str, value: AttrValue) -> None:
        self.attributes[key] = value


class TraceRecorder:
    def __init__(self) -> None:
        self._origin = time.perf_counter()
        self._spans: list[TraceSpan] = []
        self._stack: list[str] = []

    @contextmanager
    def span(self, name: str, **attributes: AttrValue) -> Generator[SpanHandle, None, None]:
        span_id = uuid.uuid4().hex[:12]
        handle = SpanHandle(span_id)
        handle.attributes.update(attributes)
        parent = self._stack[-1] if self._stack else None
        self._stack.append(span_id)
        start = time.perf_counter()
        status: str = "OK"
        try:
            yield handle
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._stack.pop()
            self._spans.append(
                TraceSpan(
                    span_id=span_id,
                    parent_span_id=parent,
                    name=name,
                    start_offset_ms=round((start - self._origin) * 1000, 3),
                    duration_ms=round((time.perf_counter() - start) * 1000, 3),
                    attributes=dict(handle.attributes),
                    status="ERROR" if status == "ERROR" else "OK",
                )
            )

    def spans(self) -> list[TraceSpan]:
        return sorted(self._spans, key=lambda s: s.start_offset_ms)
