"""Minimal telemetry helpers that can later be wired to OpenTelemetry."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Mapping

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure standard logging; can be swapped for OTLP later."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


configure_logging()


def get_logger() -> logging.Logger:
    return logging.getLogger("lewis")


@dataclass(slots=True)
class TelemetryEvent:
    name: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetryStore:
    """In-memory buffer holding recent telemetry for governance APIs."""

    def __init__(self, max_events: int = 1000) -> None:
        self._events: deque[TelemetryEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: TelemetryEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list_events(self, *, limit: int = 50, name: str | None = None) -> list[TelemetryEvent]:
        with self._lock:
            events = list(self._events)

        if name:
            events = [evt for evt in events if evt.name == name]
        return events[-limit:]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)

        counts = Counter(evt.name for evt in events)
        last_at = events[-1].timestamp if events else None
        return {
            "total_events": len(events),
            "events_by_name": dict(counts),
            "last_event_at": last_at,
        }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


telemetry_store = TelemetryStore()


def emit_event(event: TelemetryEvent) -> None:
    """Record an event using the configured logger."""
    get_logger().info("%s %s", event.name, dict(event.attributes))
    telemetry_store.record(event)
