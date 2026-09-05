from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for operation boundary logs."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def format_duration(seconds: float) -> str:
    """Format a duration in seconds into a compact human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.3f} s"
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours} h {minutes:02} m {secs:02} s"


@dataclass
class OperationLogContext:
    """
    Lightweight context for one observable operation.

    Owns operation identity, boundary timestamps, and monotonic elapsed time.
    """

    operation: str
    operation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    started_at_utc: str = field(default_factory=utc_now_iso)
    _started_at: float = field(default_factory=perf_counter, repr=False)

    @property
    def duration_seconds(self) -> float:
        return perf_counter() - self._started_at

    @property
    def duration_ms(self) -> float:
        return self.duration_seconds * 1000

    @property
    def duration_human(self) -> str:
        return format_duration(self.duration_seconds)

    def extra(self, **fields: Any) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation": self.operation,
            **fields,
        }

    def started_extra(self, **fields: Any) -> dict[str, Any]:
        return self.extra(started_at_utc=self.started_at_utc, **fields)

    def completed_extra(self, **fields: Any) -> dict[str, Any]:
        return self.extra(
            started_at_utc=self.started_at_utc,
            ended_at_utc=utc_now_iso(),
            duration_ms=round(self.duration_ms, 2),
            duration_human=self.duration_human,
            **fields,
        )
