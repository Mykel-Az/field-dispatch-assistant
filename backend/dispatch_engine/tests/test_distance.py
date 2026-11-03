"""Distance: known values, travel time, and the properties scoring relies on."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dispatch_engine.distance import (
    DEFAULT_SPEED_MPH,
    EARTH_RADIUS_MILES,
    ROAD_FACTOR,
    DistanceProvider,
    HaversineProvider,
)
from dispatch_engine.types import Location

AUSTIN = Location(30.2672, -97.7431)
DALLAS = Location(32.7767, -96.7970)

locations = st.builds(
    Location,
    lat=st.floats(-90, 90, allow_nan=False),
    lng=st.floats(-180, 180, allow_nan=False),
)


# ---- known values -----------------------------------------------------------
def test_austin_to_dallas_is_about_182_miles():
    assert HaversineProvider().miles(AUSTIN, DALLAS) == pytest.approx(182, abs=2)


def test_a_quarter_of_the_equator():
    quarter = math.pi / 2 * EARTH_RADIUS_MILES  # 0 deg to 90 deg east on the equator
    assert HaversineProvider().miles(Location(0, 0), Location(0, 90)) == pytest.approx(
        quarter
    )


def test_opposite_points_do_not_crash():
    half = math.pi * EARTH_RADIUS_MILES
    assert HaversineProvider().miles(Location(0, 0), Location(0, 180)) == pytest.approx(
        half
    )


def test_the_same_point_is_exactly_zero():
    assert HaversineProvider().miles(AUSTIN, AUSTIN) == 0.0


# ---- travel time ------------------------------------------------------------
def test_travel_time_is_miles_over_speed_with_the_road_factor():
    provider = HaversineProvider(speed_mph=30)
    miles = provider.miles(AUSTIN, DALLAS)
    assert provider.travel_minutes(AUSTIN, DALLAS) == pytest.approx(
        miles * ROAD_FACTOR / 30 * 60
    )


def test_double_the_speed_halves_the_time():
    slow, fast = HaversineProvider(30), HaversineProvider(60)
    assert fast.travel_minutes(AUSTIN, DALLAS) == pytest.approx(
        slow.travel_minutes(AUSTIN, DALLAS) / 2
    )


def test_no_travel_takes_no_time():
    assert HaversineProvider().travel_minutes(AUSTIN, AUSTIN) == 0.0


def test_the_default_speed_is_used_when_none_is_given():
    assert HaversineProvider().speed_mph == DEFAULT_SPEED_MPH


@pytest.mark.parametrize("speed", [0, -10])
def test_a_speed_that_is_not_positive_is_refused(speed):
    with pytest.raises(ValueError, match="speed"):
        HaversineProvider(speed)


def test_haversine_satisfies_the_protocol():
    def trip(provider: DistanceProvider) -> float:
        return provider.miles(AUSTIN, DALLAS)

    assert trip(HaversineProvider()) > 0


# ---- properties (Hypothesis) ------------------------------------------------
@given(locations, locations)
def test_distance_is_symmetric(a, b):
    provider = HaversineProvider()
    assert provider.miles(a, b) == pytest.approx(provider.miles(b, a))


@given(locations, locations)
def test_distance_is_never_negative(a, b):
    assert HaversineProvider().miles(a, b) >= 0


@given(locations)
def test_distance_to_itself_is_zero(a):
    assert HaversineProvider().miles(a, a) == 0.0


@given(locations, locations, locations)
def test_going_via_a_third_point_is_never_shorter(a, b, c):
    provider = HaversineProvider()
    direct = provider.miles(a, c)
    via = provider.miles(a, b) + provider.miles(b, c)
    assert direct <= via + 1e-6  # tiny allowance for floating-point rounding
