import time
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

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


class TestFixedClockIsDeterministic:
    """The engine's invariant 14 (same input, same output) needs a clock that stands still."""

    def test_it_does_not_follow_real_time(self):
        clock = FixedClock(FIXED_INSTANT)

        first = clock.now()
        time.sleep(0.01)  # real time moves on; the fixed clock must not

        assert clock.now() == first == FIXED_INSTANT

    @given(st.datetimes(timezones=st.just(timezone.utc)))
    def test_any_aware_instant_comes_back_unchanged_every_time(self, instant):
        clock = FixedClock(instant)

        assert clock.now() == instant
        assert clock.now() == clock.now()

    def test_a_function_of_now_gives_the_same_answer_on_every_run(self):
        # Stands in for the engine until it exists: the S2-4 test repeats this
        # with a whole plan (same FixedClock in, same Plan out).
        def deadline(clock: Clock) -> datetime:
            return clock.now() + timedelta(hours=1)

        clock = FixedClock(FIXED_INSTANT)

        assert deadline(clock) == deadline(clock) == FIXED_INSTANT + timedelta(hours=1)
