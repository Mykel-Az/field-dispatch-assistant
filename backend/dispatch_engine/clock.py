"""Time for the dispatch engine.

The engine never reads the system time itself: "now" is an input, so the same
input and config always give the same plan (invariant 14). The clock is injected
instead. `SystemClock` is for the app, `FixedClock` is for tests.
"""

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """A source of timezone-aware times for the engine."""

    def now(self) -> datetime: ...


class SystemClock:
    """A clock that returns the current time in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Always returns the same instant, for predictable tests."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant must be timezone-aware")

        self._instant = instant

    def now(self) -> datetime:
        return self._instant
