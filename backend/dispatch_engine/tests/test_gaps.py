"""Gap insertion (ADR-027): new jobs fit in the free time between a technician's fixed jobs."""

import itertools
from datetime import timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from dispatch_engine.assignment import assign_jobs
from dispatch_engine.clock import FixedClock
from dispatch_engine.types import Commitment, Location, SlaLabel

from .builders import HERE, NOW, StubDistance, make_config, make_job, make_tech

CLOCK = FixedClock(NOW)
THERE = Location(30.4, -97.6)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def busy_tech(*stretches, **overrides):
    """A technician whose day already holds `stretches` = (start, end) minutes after NOW."""
    commitments = tuple(Commitment(at(a), at(b), THERE) for a, b in stretches)
    return make_tech(
        free_at=max(c.end for c in commitments),
        position=THERE,
        assigned_count=len(commitments),
        commitments=commitments,
        home=HERE,
        **overrides,
    )


def urgent(id=1, duration=60):
    return make_job(
        id=id,
        label=f"Job {id}",
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        duration_minutes=duration,
    )


def run(jobs, techs, travel=11):
    return assign_jobs(jobs, techs, make_config(), StubDistance(travel), CLOCK)


def arrival_of(plan, job_id):
    return next(a for a in plan.assignments if a.job_id == job_id).estimated_arrival


def test_an_urgent_job_goes_before_a_fixed_job_later_in_the_day():
    # Breaker job 14:00-16:00 (5h to 7h after 09:00). The urgent job fits long before it.
    plan = run([urgent()], [busy_tech((300, 420))])
    assert arrival_of(plan, 1) == at(11)
    assert plan.assignments[0].sla_label != SlaLabel.BREACH


def test_without_the_gap_search_it_would_have_been_after_the_fixed_job():
    # Same day, but the fixed job is right now: no gap, so the job goes after it (+11 drive).
    plan = run([urgent()], [busy_tech((0, 120))])
    assert arrival_of(plan, 1) == at(120 + 11)


def test_the_gap_must_hold_the_drive_in_the_job_and_the_drive_on():
    # 11 to get there + 60 on the job + 11 on to the next job = 82 minutes.
    assert arrival_of(run([urgent()], [busy_tech((82, 200))]), 1) == at(11)
    assert arrival_of(run([urgent()], [busy_tech((81, 200))]), 1) == at(200 + 11)


def test_two_new_jobs_use_the_gap_one_after_the_other():
    plan = run([urgent(1), urgent(2)], [busy_tech((300, 420))])
    arrivals = sorted([arrival_of(plan, 1), arrival_of(plan, 2)])
    assert arrivals == [at(11), at(11 + 60 + 11)]


def test_a_third_job_that_no_longer_fits_goes_after_the_fixed_job():
    # Gap is 0..120: room for one 60-minute job (11+60+11=82), not two (82+71 > 120).
    plan = run([urgent(1), urgent(2)], [busy_tech((120, 200))])
    assert sorted([arrival_of(plan, 1), arrival_of(plan, 2)]) == [at(11), at(200 + 11)]


def test_a_commitment_that_is_already_over_blocks_nothing():
    over = Commitment(at(-120), at(-60), THERE)
    tech = make_tech(
        free_at=at(-60),
        position=THERE,
        assigned_count=1,
        commitments=(over,),
        home=HERE,
    )
    assert arrival_of(run([urgent()], [tech]), 1) == at(11)


def test_a_job_that_starts_at_the_closing_time_of_the_gap_search_still_respects_the_shift():
    tech = busy_tech((60, 120), shift_end=at(130))
    plan = run([urgent()], [tech])
    # After the fixed job it would arrive at 131: after closing, so nobody can take it.
    assert plan.assignments == () and len(plan.unassigned) == 1


@settings(max_examples=60, deadline=None)
@given(
    stretches=st.lists(
        st.tuples(st.integers(0, 400), st.integers(20, 120)), min_size=0, max_size=3
    ),
    durations=st.lists(st.integers(10, 90), min_size=1, max_size=4),
)
def test_planned_jobs_never_overlap_the_fixed_ones_or_each_other(stretches, durations):
    # Make the existing stretches themselves non-overlapping, as the adapter does.
    cursor, spans = 0, []
    for start, length in sorted(stretches):
        start = max(start, cursor)
        spans.append((start, start + length))
        cursor = start + length
    tech = (
        busy_tech(*spans, shift_end=at(2000))
        if spans
        else make_tech(shift_end=at(2000))
    )
    jobs = [urgent(i + 1, d) for i, d in enumerate(durations)]
    plan = run(jobs, [tech], travel=0)
    taken = [(at(a), at(b)) for a, b in spans]
    length = {i + 1: timedelta(minutes=d) for i, d in enumerate(durations)}
    for a in plan.assignments:
        taken.append((a.estimated_arrival, a.estimated_arrival + length[a.job_id]))
    taken.sort()
    for (_, end), (start, _) in itertools.pairwise(taken):
        assert end <= start
