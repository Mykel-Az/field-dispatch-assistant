from datetime import datetime, timezone

import pytest

from dispatch_engine.clock import Clock, FixedClock, SystemClock

# Shared test datetime
FIXED_INSTANT = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


class TestFixedClock:
    def test_now_returns_the_suppled_instant(self):
        clock = FixedClock(FIXED_INSTANT)

        assert clock.now() == FIXED_INSTANT

    def test_multiple_calls_return_the_same_instant(self):
        clock = FixedClock(FIXED_INSTANT)

        first_call = clock.now()
        second_call = clock.now()

        assert first_call == second_call

    def test_rejects_naive_datetime(self):
        naive_datetime = datetime(2026, 11, 3, 9, 0)  # noqa: DTZ001  (on purpose: no time zone)

        with pytest.raises(ValueError, match="timezone-aware"):
            FixedClock(naive_datetime)


class TestSystemClock:
    def test_now_returns_timezone_aware_datetime(self):
        clock = SystemClock()

        result = clock.now()

        assert result.tzinfo is not None
        assert result.utcoffset() is not None

    def test_now_returns_time_between_two_real_time_readings(self):
        clock = SystemClock()

        before = datetime.now(timezone.utc)
        result = clock.now()
        after = datetime.now(timezone.utc)

        assert before <= result <= after


class TestClockProtocol:
    def test_system_clock_satisfies_clock_protocol(self):
        def get_time(clock: Clock) -> datetime:
            return clock.now()

        result = get_time(SystemClock())

        assert isinstance(result, datetime)

    def test_fixed_clock_satisfies_clock_protocol(self):
        def get_time(clock: Clock) -> datetime:
            return clock.now()

        result = get_time(FixedClock(FIXED_INSTANT))

        assert result == FIXED_INSTANT
