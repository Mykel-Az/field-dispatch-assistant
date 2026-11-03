"""
The engine must never read the system time itself. Invariant 14 says the same input and config give the same output. so we use dependency injection.
i.e: object from external source instead of internal
"""

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """returns consistent, timezone-aware source of time to the engine"""

    def now(self) -> datetime: ...


class SystemClock:
    """A clock that returns the current time in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """returns a fixed time, useful for predictabe execution and testing"""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("instant must be timezone-aware")

        self._instant = instant

    def now(self) -> datetime:
        return self._instant
