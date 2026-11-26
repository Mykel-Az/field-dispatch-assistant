"""SEQUENCE: driving order within a technician's day (ADR-003, ADR-028)."""

import random
from datetime import timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from dispatch_engine.assignment import assign_jobs
from dispatch_engine.clock import FixedClock
from dispatch_engine.distance import HaversineProvider
from dispatch_engine.sequencing import _nearest_first, sequence_plan, sequence_route
from dispatch_engine.types import Commitment, Location, ReasonCode, SlaLabel

from .builders import NOW, make_config, make_job, make_tech

CLOCK = FixedClock(NOW)
DISTANCE = HaversineProvider(speed_mph=30.0)
BASE = Location(30.0, -97.0)


def at(minutes: int):
    return NOW + timedelta(minutes=minutes)


def job(id, east_miles, *, start=0, end=480, **overrides):
    """A job `east_miles` east of the start point, window start..end minutes after NOW."""
    return make_job(
        id=id,
        label=f"Job {id}",
        location=Location(30.0, -97.0 + east_miles / 59.9),
        slot_start=at(start),
        slot_end=at(end),
        duration_minutes=30,
        **overrides,
    )


def tech(**overrides):
    return make_tech(**{"position": BASE, "skill_ids": frozenset({1}), **overrides})


def plan_and_sequence(jobs, techs=None, config=None):
    techs = techs or [tech()]
    config = config or make_config()
    plan = assign_jobs(jobs, techs, config, DISTANCE, CLOCK)
    return sequence_plan(plan, jobs, techs, config, DISTANCE, CLOCK), plan


def order_for(plan, technician_id=1):
    return [a.job_id for a in plan.assignments if a.technician_id == technician_id]


def test_wide_windows_are_driven_nearest_first():
    # Deadlines make ASSIGN go 1 (far), 2 (near), 3 (middle); distance says 2, 3, 1.
    jobs = [
        job(1, 20, end=300),
        job(2, 1, end=310),
        job(3, 10, end=320),
    ]
    sequenced, assigned = plan_and_sequence(jobs)
    assert order_for(assigned) == [1, 2, 3]
    assert order_for(sequenced) == [2, 3, 1]


def test_the_first_stop_is_nearest_the_start_unless_its_window_forbids_it():
    # Job 2 is nearest but opens only at +300 min; going to it first would be late for
    # job 1 (due at +90). Job 1 must go first even though it is farther.
    jobs = [job(1, 15, end=90), job(2, 1, start=300, end=480)]
    sequenced, _ = plan_and_sequence(jobs)
    assert order_for(sequenced) == [1, 2]


def test_a_fixed_window_never_starts_early():
    jobs = [job(1, 5, start=120, end=300), job(2, 6, start=0, end=300)]
    sequenced, _ = plan_and_sequence(jobs)
    by_id = {a.job_id: a for a in sequenced.assignments}
    assert by_id[1].estimated_arrival >= at(120)


def test_an_urgent_job_goes_first_when_it_can():
    jobs = [job(1, 1, end=480), job(2, 30, end=480)]
    urgent = make_job(
        id=3,
        label="Job 3",
        location=Location(30.0, -97.0 + 25 / 59.9),
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        created_at=NOW,
        duration_minutes=30,
    )
    sequenced, _ = plan_and_sequence([*jobs, urgent])
    assert order_for(sequenced)[0] == 3


def test_sequencing_never_changes_who_does_a_job_or_drops_one():
    jobs = [job(i, i * 3, end=400 + i) for i in range(1, 7)]
    techs = [tech(id=1), tech(id=2, label="Ana")]
    sequenced, assigned = plan_and_sequence(jobs, techs)
    assert {(a.job_id, a.technician_id) for a in sequenced.assignments} == {
        (a.job_id, a.technician_id) for a in assigned.assignments
    }
    assert sequenced.unassigned == assigned.unassigned


def test_it_keeps_the_order_when_nearest_first_would_not_help():
    jobs = [job(1, 1, end=100), job(2, 5, end=200), job(3, 9, end=300)]
    sequenced, assigned = plan_and_sequence(jobs)
    assert order_for(sequenced) == order_for(assigned) == [1, 2, 3]
    stop = next(
        r
        for r in sequenced.assignments[0].explanation.reasons
        if r.code == ReasonCode.STOP_ORDER
    )
    assert stop.facts["reordered"] == 0


def test_the_explanation_is_restated_for_the_new_order():
    jobs = [job(1, 20, end=300), job(2, 1, end=310), job(3, 10, end=320)]
    sequenced, _ = plan_and_sequence(jobs)
    first = sequenced.assignments[0]
    reasons = {r.code: r.facts for r in first.explanation.reasons}
    assert first.job_id == 2
    assert reasons[ReasonCode.STOP_ORDER] == {
        "stop": 1,
        "stops": 3,
        "previous_job_id": 0,
        "drive_minutes": reasons[ReasonCode.ASSIGNED]["travel_minutes"],
        "reordered": 1,
    }
    second = sequenced.assignments[1]
    stop = next(
        r.facts for r in second.explanation.reasons if r.code == ReasonCode.STOP_ORDER
    )
    assert stop["previous_job_id"] == 2 and stop["stop"] == 2


def test_labels_and_slack_follow_the_new_arrival():
    jobs = [job(1, 1, end=61), job(2, 2, end=480)]  # job 1 due 1 h after NOW, tight
    sequenced, _ = plan_and_sequence(jobs)
    for a in sequenced.assignments:
        assert (a.slack_minutes < 0) == (a.sla_label == SlaLabel.BREACH)


def test_existing_jobs_set_where_and_when_the_technician_starts():
    busy = tech(free_at=at(120), position=Location(30.0, -97.0 + 40 / 59.9))
    jobs = [job(1, 41, end=480), job(2, 1, end=480)]
    sequenced, _ = plan_and_sequence(jobs, [busy])
    first = sequenced.assignments[0]
    assert first.job_id == 1  # nearest to where they will be, not to the workstation
    assert first.estimated_arrival >= at(120)


def test_a_single_job_route_is_unchanged():
    sequenced, assigned = plan_and_sequence([job(1, 5)])
    assert sequenced.assignments[0].estimated_arrival == (
        assigned.assignments[0].estimated_arrival
    )


def test_an_empty_plan_stays_empty():
    sequenced, _ = plan_and_sequence([])
    assert sequenced.assignments == () and sequenced.unassigned == ()


def test_nearest_first_does_not_take_a_near_job_that_makes_a_tight_one_late():
    # Job 2 is 1 mile away but takes an hour; job 1 is 10 miles away and due in 60 min.
    # Going to job 2 first would reach job 1 about 86 min in, so job 1 goes first.
    tight = job(1, 10, end=60)
    near = make_job(
        id=2,
        label="Job 2",
        location=Location(30.0, -97.0 + 1 / 59.9),
        slot_start=at(0),
        slot_end=at(480),
        duration_minutes=60,
    )
    route = _nearest_first([tight, near], tech(), make_config(), DISTANCE, NOW)
    assert [s.job.id for s in route.stops] == [1, 2]
    assert route.late_minutes == 0


def test_the_given_order_is_kept_when_greedy_nearest_would_drive_more():
    # On a line: start 0, A at +2, B at -3, C at +12. Greedy goes A, B, C (22 miles of
    # driving); B, A, C is 18. The given order B, A, C must not be replaced.
    jobs = [job(2, -3), job(1, 2), job(3, 12)]
    route, changed = sequence_route(jobs, tech(), make_config(), DISTANCE, NOW)
    assert [s.job.id for s in route.stops] == [2, 1, 3]
    assert not changed


def test_a_better_order_is_reported_as_changed():
    jobs = [job(1, 20, end=300), job(2, 1, end=310), job(3, 10, end=320)]
    route, changed = sequence_route(jobs, tech(), make_config(), DISTANCE, NOW)
    assert changed and [s.job.id for s in route.stops] == [2, 3, 1]


# ---- properties -------------------------------------------------------------
jobs_strategy = st.lists(
    st.tuples(
        st.integers(0, 40),  # miles east
        st.integers(0, 300),  # window start (minutes)
        st.integers(60, 400),  # window length
        st.sampled_from([30, 45, 60]),
    ),
    min_size=1,
    max_size=7,
)


def build(specs):
    return [
        make_job(
            id=i + 1,
            label=f"Job {i + 1}",
            location=Location(30.0, -97.0 + east / 59.9),
            slot_start=at(start),
            slot_end=at(start + length),
            duration_minutes=dur,
        )
        for i, (east, start, length, dur) in enumerate(specs)
    ]


def total_late(plan):
    return sum(max(0.0, -a.slack_minutes) for a in plan.assignments)


@settings(max_examples=60, deadline=None)
@given(jobs_strategy)
def test_sequencing_is_never_later_overall_than_assign(specs):
    jobs = build(specs)
    sequenced, assigned = plan_and_sequence(
        jobs, config=make_config(max_jobs_per_tech_per_day=8)
    )
    assert total_late(sequenced) <= total_late(assigned) + 1e-6


@settings(max_examples=60, deadline=None)
@given(jobs_strategy)
def test_one_technicians_stops_never_overlap_and_never_start_before_the_window(specs):
    jobs = build(specs)
    by_id = {j.id: j for j in jobs}
    sequenced, _ = plan_and_sequence(
        jobs, config=make_config(max_jobs_per_tech_per_day=8)
    )
    previous_end = None
    for a in sequenced.assignments:
        j = by_id[a.job_id]
        assert a.estimated_arrival >= j.slot_start
        if previous_end is not None:
            assert a.estimated_arrival >= previous_end
        previous_end = a.estimated_arrival + timedelta(minutes=j.duration_minutes)


@settings(max_examples=40, deadline=None)
@given(jobs_strategy, st.randoms(use_true_random=False))
def test_the_order_does_not_depend_on_the_order_jobs_are_passed_in(specs, rnd):
    jobs = build(specs)
    shuffled = list(jobs)
    random.Random(rnd.random()).shuffle(shuffled)
    config = make_config(max_jobs_per_tech_per_day=8)
    a, _ = plan_and_sequence(jobs, config=config)
    b, _ = plan_and_sequence(shuffled, config=config)
    assert order_for(a) == order_for(b)


# ---- fixed commitments (ADR-027) ---------------------------------------------------


def test_sequencing_never_overlaps_an_existing_commitment():
    """A technician has a fixed job from 120 to 180 min; new jobs fit around it, never on it."""
    fixed = Commitment(at(120), at(180), Location(30.0, -97.0 + 2 / 59.9))
    busy = tech(commitments=(fixed,), free_at=at(180), position=fixed.location)
    jobs = [job(1, 1, end=600), job(2, 4, end=600), job(3, 2, end=600)]
    sequenced, _ = plan_and_sequence(jobs, [busy])
    assert len(sequenced.assignments) == 3
    for a in sequenced.assignments:
        j = next(j for j in jobs if j.id == a.job_id)
        end = a.estimated_arrival + timedelta(minutes=j.duration_minutes)
        assert end <= fixed.start or a.estimated_arrival >= fixed.end


def test_assignments_are_listed_in_the_order_the_day_runs():
    """With a gap, a job planned later can be driven earlier: the list follows the clock."""
    fixed = Commitment(at(240), at(300), Location(30.0, -97.0 + 3 / 59.9))
    busy = tech(commitments=(fixed,), free_at=at(300), position=fixed.location)
    jobs = [job(1, 1, end=600), job(2, 2, end=600)]
    sequenced, _ = plan_and_sequence(jobs, [busy])
    arrivals = [a.estimated_arrival for a in sequenced.assignments]
    assert arrivals == sorted(arrivals)
