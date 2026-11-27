"""Before and after: hand-computed numbers on a tiny map (ADR-030)."""

from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dispatch_engine.distance import HaversineProvider
from dispatch_engine.metrics import compare, measure, round_robin
from dispatch_engine.types import Location

from .builders import NOW, make_config, make_job, make_tech

DISTANCE = HaversineProvider(speed_mph=30.0)
# One degree of latitude is 69.09 miles, so 0.1 degree is 6.909 miles: easy to check.
DEGREE_MILES = 69.09
BASE = Location(30.0, -97.0)


def north(tenths: float) -> Location:
    return Location(30.0 + tenths / 10, -97.0)


def south(tenths: float) -> Location:
    return Location(30.0 - tenths / 10, -97.0)


def job(job_id, where, skills=frozenset({1}), **over):
    fields = {
        "id": job_id,
        "location": where,
        "acceptable_skill_ids": skills,
        "slot_start": NOW,
        "slot_end": NOW + timedelta(hours=8),
    }
    return make_job(**{**fields, **over})


def tech(tech_id, where=BASE, skills=frozenset({1})):
    return make_tech(
        id=tech_id, label=f"T{tech_id}", position=where, home=where, skill_ids=skills
    )


# ---- round robin ----------------------------------------------------------------
def test_round_robin_deals_in_turn_by_request_order():
    routes, left = round_robin(
        [job(3, BASE), job(1, BASE), job(2, BASE), job(4, BASE)], [tech(2), tech(1)]
    )
    assert routes == {1: [job(1, BASE), job(3, BASE)], 2: [job(2, BASE), job(4, BASE)]}
    assert left == []


def test_round_robin_skips_a_technician_without_the_skill():
    plumber = tech(2, skills=frozenset({9}))
    routes, _ = round_robin([job(1, BASE), job(2, BASE)], [tech(1), plumber])
    assert [j.id for j in routes[1]] == [1, 2] and routes[2] == []


def test_a_job_nobody_has_the_skill_for_is_unplaced():
    routes, left = round_robin([job(1, BASE, skills=frozenset({7}))], [tech(1)])
    assert routes[1] == [] and [j.id for j in left] == [1]


# ---- measuring ------------------------------------------------------------------
def test_travel_is_the_drive_from_the_workstation_through_every_stop():
    result = measure(
        {1: [job(1, north(1)), job(2, north(3))]},
        [tech(1)],
        make_config(),
        DISTANCE,
        NOW,
    )
    assert result.travel_miles == pytest.approx(0.3 * DEGREE_MILES, abs=0.1)  # 20.7
    assert (result.jobs, result.sla_breaches, result.late_minutes) == (2, 0, 0)


def test_a_late_arrival_is_a_breach_and_its_minutes_are_counted():
    # 0.5 degree = 34.5 miles x 1.3 / 30 mph = about 89.7 min away, window closes at +60.
    far = job(1, north(5), slot_start=NOW, slot_end=NOW + timedelta(minutes=60))
    result = measure({1: [far]}, [tech(1)], make_config(), DISTANCE, NOW)
    assert result.sla_breaches == 1
    assert result.late_minutes == pytest.approx(30, abs=1)


def test_workload_spread_is_most_minus_fewest_over_all_technicians():
    result = measure(
        {1: [job(1, BASE), job(2, BASE), job(3, BASE)]},
        [tech(1), tech(2)],
        make_config(),
        DISTANCE,
        NOW,
    )
    assert (result.min_jobs, result.max_jobs, result.workload_spread) == (0, 3, 3)


# ---- the comparison -------------------------------------------------------------
def test_assigning_by_area_drives_less_than_dealing_round_robin():
    """Two jobs just north of one technician and two just south of the other.

    The plan sends each pair to the technician beside it: 0 + 6.9 miles each, 13.8 in all.
    Round-robin deals 1->T1, 2->T2, 3->T1, 4->T2, so each technician crosses town:
    T1 north(5)->south(5) 69.1, T2 south(5)->north(6) 76.0 then north(6)->south(6) 82.9.
    """
    north_tech, south_tech = tech(1, north(5)), tech(2, south(5))
    jobs = [job(1, north(5)), job(2, north(6)), job(3, south(5)), job(4, south(6))]
    plan = {1: [jobs[0], jobs[1]], 2: [jobs[2], jobs[3]]}
    after, before = compare(
        plan, jobs, [north_tech, south_tech], make_config(), DISTANCE, NOW
    )
    assert after.travel_miles == pytest.approx(13.8, abs=0.2)
    assert before.travel_miles == pytest.approx(228.0, abs=1.5)
    assert after.travel_miles < before.travel_miles


def test_the_same_plan_compared_with_itself_has_equal_numbers():
    jobs = [job(1, north(1)), job(2, north(2))]
    deal, _ = round_robin(jobs, [tech(1)])
    after, before = compare(deal, jobs, [tech(1)], make_config(), DISTANCE, NOW)
    assert after == before


@given(st.lists(st.integers(1, 40), min_size=1, max_size=12, unique=True))
def test_round_robin_places_every_job_exactly_once(ids):
    jobs = [job(i, BASE) for i in ids]
    routes, left = round_robin(jobs, [tech(1), tech(2), tech(3)])
    placed = [j.id for route in routes.values() for j in route]
    assert sorted(placed + [j.id for j in left]) == sorted(ids) and left == []
    sizes = sorted(len(r) for r in routes.values())
    assert sizes[-1] - sizes[0] <= 1  # dealt evenly
