"""ASSIGN: order, choice, the technician's day moving forward, and the expected 'nobody' outcome."""

import random
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dispatch_engine.assignment import assign_jobs
from dispatch_engine.clock import FixedClock
from dispatch_engine.types import Location, Priority, ReasonCode, SlaLabel

from .builders import NOW, StubDistance, make_config, make_job, make_tech

CLOCK = FixedClock(NOW)


def at(minutes: int):
    return NOW + timedelta(minutes=minutes)


def job(id, *, start=0, end=240, **overrides):
    """A job with a window from `start` to `end` minutes after NOW."""
    return make_job(
        id=id, label=f"Job {id}", slot_start=at(start), slot_end=at(end), **overrides
    )


def urgent(id, **overrides):
    return make_job(
        id=id,
        label=f"Job {id}",
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        **overrides,
    )


def run(jobs, techs, config=None, distance=None):
    return assign_jobs(
        jobs, techs, config or make_config(), distance or StubDistance(0), CLOCK
    )


def assigned(plan):
    return {a.job_id: a.technician_id for a in plan.assignments}


class ByPosition:
    """Travel minutes depend on where the technician is, so tests can make one closer."""

    def __init__(self, minutes_by_position, default=10.0):
        self.minutes_by_position = minutes_by_position
        self.default = default
        self.calls = []

    def miles(self, a, b):
        return 0.0

    def travel_minutes(self, a, b):
        self.calls.append((a, b))
        return self.minutes_by_position.get(a, self.default)


# ---- who gets the job -------------------------------------------------------
def test_the_best_scored_technician_gets_the_job():
    near, far = Location(30.3, -97.7), Location(31.0, -97.7)
    distance = ByPosition({near: 5, far: 40})
    techs = [make_tech(id=1, position=far), make_tech(id=2, position=near)]
    plan = run([job(10)], techs, make_config(scoring_strategy="nearest"), distance)
    assert assigned(plan) == {10: 2}


def test_equal_technicians_are_tied_by_lowest_id():
    plan = run([job(10)], [make_tech(id=3), make_tech(id=1), make_tech(id=2)])
    assert assigned(plan) == {10: 1}


# ---- the order jobs are handled in ------------------------------------------
def test_an_urgent_job_beats_a_normal_one_when_only_one_fits():
    tech = make_tech(shift_end=at(30))  # can start one job, not two
    plan = run([job(1, start=0, end=120), urgent(2)], [tech])
    assert assigned(plan) == {2: 1}
    assert [u.job_id for u in plan.unassigned] == [1]


def test_higher_priority_goes_first_when_deadlines_are_equal():
    tech = make_tech(shift_end=at(30))
    jobs = [
        job(1, priority=Priority.NORMAL),
        job(2, priority=Priority.HIGH),
        job(3, priority=Priority.LOW),
    ]
    plan = run(jobs, [tech])
    assert assigned(plan) == {2: 1}


def test_priority_beats_an_earlier_deadline():
    tech = make_tech(shift_end=at(30))
    plan = run([job(1, end=60), job(2, end=240, priority=Priority.HIGH)], [tech])
    assert assigned(plan) == {2: 1}


def test_the_earliest_deadline_goes_first_so_the_day_moves_forward():
    """A 3 pm job with a lower id must not push the 9 am job into the afternoon."""
    afternoon = job(1, start=360, end=480)  # 3 pm to 5 pm
    morning = job(2, start=0, end=120)  # 9 am to 11 am
    plan = run([afternoon, morning], [make_tech()])
    assert [a.job_id for a in plan.assignments] == [2, 1]
    assert all(a.sla_label == SlaLabel.OK for a in plan.assignments)
    assert plan.assignments[0].estimated_arrival == at(0)
    assert plan.assignments[1].estimated_arrival == at(360)


def test_an_anytime_job_with_closing_time_as_its_deadline_goes_last():
    anytime = job(1, start=0, end=480, slot_is_fixed=False)
    fixed = job(2, start=0, end=120)
    plan = run([anytime, fixed], [make_tech()])
    assert [a.job_id for a in plan.assignments] == [2, 1]


# ---- the technician's day moves on after each assignment --------------------
def test_a_second_job_starts_after_the_first_one_ends():
    plan = run([job(1, end=300), job(2, end=300)], [make_tech()])
    first, second = plan.assignments
    assert second.estimated_arrival >= first.estimated_arrival + timedelta(minutes=60)


def test_the_next_trip_starts_from_the_last_job():
    distance = ByPosition({}, default=10.0)
    first_place, second_place = Location(30.3, -97.7), Location(30.4, -97.6)
    start = Location(30.2, -97.8)
    jobs = [
        job(1, end=100, location=first_place),
        job(2, end=300, location=second_place),
    ]
    run(jobs, [make_tech(position=start)], distance=distance)
    assert distance.calls == [(start, first_place), (first_place, second_place)]


def test_load_from_the_first_job_sends_the_second_to_the_other_technician():
    jobs = [job(1, end=300), job(2, end=300)]
    plan = run(
        jobs,
        [make_tech(id=1), make_tech(id=2)],
        make_config(scoring_strategy="balanced"),
    )
    assert assigned(plan) == {1: 1, 2: 2}


# ---- nobody can take it (expected, not an error) ----------------------------
def test_a_job_nobody_can_take_is_listed_with_a_reason_for_every_technician():
    techs = [
        make_tech(id=1, skill_ids=frozenset({9})),
        make_tech(id=2, is_available=False),
        make_tech(id=3, shift_end=at(5)),
    ]
    plan = run([job(10, start=30, end=120)], techs)
    assert plan.assignments == ()
    (missed,) = plan.unassigned
    codes = [r.code for r in missed.explanation.reasons]
    assert codes == [
        ReasonCode.NO_FEASIBLE_TECHNICIAN,
        ReasonCode.SKILL_MISMATCH,
        ReasonCode.UNAVAILABLE,
        ReasonCode.AFTER_CLOSING,
    ]


def test_no_technicians_at_all_is_an_unassigned_job_not_a_crash():
    plan = run([job(10)], [])
    (missed,) = plan.unassigned
    assert missed.explanation.reasons[0].facts["technicians_checked"] == 0


def test_an_unassignable_job_does_not_block_the_others():
    jobs = [job(1, acceptable_skill_ids=frozenset({99})), job(2)]
    plan = run(jobs, [make_tech()])
    assert assigned(plan) == {2: 1}
    assert [u.job_id for u in plan.unassigned] == [1]


def test_no_jobs_gives_an_empty_plan():
    plan = run([], [make_tech()])
    assert plan.assignments == () and plan.unassigned == ()


# ---- late and loaded assignments are still made, and say so -----------------
def test_a_job_that_cannot_make_its_window_is_still_assigned_and_flagged():
    tech = make_tech(free_at=at(60))
    plan = run([job(1, start=0, end=30)], [tech])
    (a,) = plan.assignments
    assert a.sla_label == SlaLabel.BREACH
    assert ReasonCode.SLA_BREACH in [r.code for r in a.explanation.reasons]


# ---- the daily limit (ADR-022) -----------------------------------------------
def codes(explanation):
    return [r.code for r in explanation.reasons]


def test_a_normal_job_never_goes_to_a_technician_at_the_limit():
    plan = run(
        [job(1)],
        [make_tech(assigned_count=3)],
        make_config(max_jobs_per_tech_per_day=3),
    )
    assert plan.assignments == ()
    assert ReasonCode.DAILY_LIMIT in codes(plan.unassigned[0].explanation)


def test_a_normal_job_goes_to_the_technician_under_the_limit_even_if_farther():
    near, far = Location(30.3, -97.7), Location(31.0, -97.7)
    techs = [
        make_tech(id=1, position=near, assigned_count=3),
        make_tech(id=2, position=far),
    ]
    plan = run(
        [job(10)],
        techs,
        make_config(scoring_strategy="nearest", max_jobs_per_tech_per_day=3),
        ByPosition({near: 2, far: 40}),
    )
    assert assigned(plan) == {10: 2}


def test_the_limit_fills_up_during_the_run():
    jobs = [job(i, end=480) for i in (1, 2, 3, 4)]
    plan = run(jobs, [make_tech()], make_config(max_jobs_per_tech_per_day=3))
    assert len(plan.assignments) == 3
    assert [u.job_id for u in plan.unassigned] == [4]


def test_an_urgent_job_prefers_a_technician_under_the_limit_even_if_farther():
    near, far = Location(30.3, -97.7), Location(30.5, -97.7)
    techs = [
        make_tech(id=1, position=near, assigned_count=3),
        make_tech(id=2, position=far),
    ]
    plan = run(
        [urgent(10)],
        techs,
        make_config(scoring_strategy="nearest", max_jobs_per_tech_per_day=3),
        ByPosition({near: 2, far: 10}),
    )
    assert assigned(plan) == {10: 2}
    assert ReasonCode.URGENT_OVER_LIMIT not in codes(plan.assignments[0].explanation)


def test_an_urgent_job_goes_over_the_limit_when_all_technicians_are_at_it():
    techs = [make_tech(id=1, assigned_count=3), make_tech(id=2, assigned_count=3)]
    plan = run([urgent(10)], techs, make_config(max_jobs_per_tech_per_day=3))
    assert len(plan.assignments) == 1
    reasons = plan.assignments[0].explanation.reasons
    over = next(r for r in reasons if r.code == ReasonCode.URGENT_OVER_LIMIT)
    assert over.facts["under_limit_candidates"] == 0


def test_an_urgent_job_goes_over_the_limit_when_the_others_would_be_late():
    """Technician 1 is under the limit but busy for 50 minutes; technician 2 is free."""
    techs = [
        make_tech(id=1, assigned_count=1, free_at=at(50)),
        make_tech(id=2, assigned_count=3),
    ]
    plan = run([urgent(10)], techs, make_config(max_jobs_per_tech_per_day=3))
    assert assigned(plan) == {10: 2}
    reasons = plan.assignments[0].explanation.reasons
    over = next(r for r in reasons if r.code == ReasonCode.URGENT_OVER_LIMIT)
    assert over.facts["under_limit_candidates"] == 1


def test_an_urgent_job_stays_under_the_limit_when_going_over_would_not_help():
    """Both would be equally late, so there is no reason to overload anyone."""
    techs = [
        make_tech(id=1, assigned_count=1, free_at=at(50)),
        make_tech(id=2, assigned_count=3, free_at=at(50)),
    ]
    plan = run([urgent(10)], techs, make_config(max_jobs_per_tech_per_day=3))
    assert assigned(plan) == {10: 1}


def test_an_urgent_job_still_fits_after_the_normal_jobs_filled_the_limit():
    jobs = [job(1, end=480), job(2, end=480), urgent(3)]
    plan = run(jobs, [make_tech()], make_config(max_jobs_per_tech_per_day=2))
    assert {3, 1}.issubset({a.job_id for a in plan.assignments})
    assert len(plan.assignments) == 2  # the urgent one first, then one normal job
    assert [u.job_id for u in plan.unassigned] == [2]


# ---- bad input --------------------------------------------------------------
def test_duplicate_job_ids_are_refused():
    with pytest.raises(ValueError, match="duplicate job"):
        run([job(1), job(1)], [make_tech()])


def test_duplicate_technician_ids_are_refused():
    with pytest.raises(ValueError, match="duplicate technician"):
        run([job(1)], [make_tech(id=1), make_tech(id=1)])


# ---- the clock --------------------------------------------------------------
def test_the_clock_is_read_once_per_run():
    class CountingClock(FixedClock):
        reads = 0

        def now(self):
            type(self).reads += 1
            return super().now()

    run_with = assign_jobs(
        [job(1), job(2)],
        [make_tech()],
        make_config(),
        StubDistance(0),
        CountingClock(NOW),
    )
    assert CountingClock.reads == 1
    assert len(run_with.assignments) == 2


def test_the_same_fixed_clock_gives_the_same_plan():
    jobs = [job(1), job(2, end=100), urgent(3)]
    techs = [make_tech(id=1), make_tech(id=2)]
    assert run(jobs, techs) == run(jobs, techs)


def test_a_later_clock_pushes_arrivals_later():
    later = assign_jobs(
        [job(1, end=600)],
        [make_tech()],
        make_config(),
        StubDistance(0),
        FixedClock(at(120)),
    )
    assert later.assignments[0].estimated_arrival == at(120)


# ---- properties (Hypothesis) ------------------------------------------------
@st.composite
def scenarios(draw):
    job_rows = draw(
        st.lists(
            st.tuples(
                st.booleans(),  # urgent
                st.sampled_from(list(Priority)),
                st.frozensets(st.integers(1, 3)),  # acceptable skills
                st.integers(15, 120),  # duration
                st.integers(0, 400),  # window start
                st.integers(30, 300),  # window length
            ),
            max_size=8,
        )
    )
    tech_rows = draw(
        st.lists(
            st.tuples(
                st.frozensets(st.integers(1, 3)),  # skills
                st.booleans(),  # available
                st.integers(60, 600),  # shift length
                st.integers(0, 4),  # jobs already
            ),
            max_size=4,
        )
    )
    jobs = []
    for i, (is_urgent, priority, skills, duration, start, length) in enumerate(
        job_rows, start=1
    ):
        if is_urgent:
            jobs.append(
                urgent(
                    i,
                    priority=priority,
                    acceptable_skill_ids=skills,
                    duration_minutes=duration,
                )
            )
        else:
            jobs.append(
                job(
                    i,
                    start=start,
                    end=start + length,
                    priority=priority,
                    acceptable_skill_ids=skills,
                    duration_minutes=duration,
                )
            )
    techs = [
        make_tech(
            id=i,
            skill_ids=skills,
            is_available=available,
            shift_end=at(length),
            assigned_count=n,
        )
        for i, (skills, available, length, n) in enumerate(tech_rows, start=1)
    ]
    return jobs, techs, draw(st.integers(0, 60))


@given(scenarios(), st.sampled_from(["nearest", "balanced"]))
def test_every_job_is_assigned_to_one_technician_or_listed_once(
    scenario, strategy
):  # inv. 1
    jobs, techs, travel = scenario
    plan = run(
        jobs, techs, make_config(scoring_strategy=strategy), StubDistance(travel)
    )
    seen = [a.job_id for a in plan.assignments] + [u.job_id for u in plan.unassigned]
    assert sorted(seen) == sorted(j.id for j in jobs)


@given(scenarios())
def test_assigned_technicians_have_a_matching_skill_and_arrive_before_closing(
    scenario,
):  # inv. 2, 5
    jobs, techs, travel = scenario
    plan = run(jobs, techs, distance=StubDistance(travel))
    jobs_by_id = {j.id: j for j in jobs}
    techs_by_id = {t.id: t for t in techs}
    for a in plan.assignments:
        tech = techs_by_id[a.technician_id]
        assert tech.is_available
        assert tech.skill_ids & jobs_by_id[a.job_id].acceptable_skill_ids
        assert a.estimated_arrival <= tech.shift_end


@given(scenarios())
def test_a_technicians_jobs_never_overlap(scenario):  # inv. 6
    jobs, techs, travel = scenario
    plan = run(jobs, techs, distance=StubDistance(travel))
    durations = {j.id: j.duration_minutes for j in jobs}
    last_end = {}
    for a in plan.assignments:  # in the order they were planned
        if a.technician_id in last_end:
            assert a.estimated_arrival >= last_end[a.technician_id]
        last_end[a.technician_id] = a.estimated_arrival + timedelta(
            minutes=durations[a.job_id]
        )


@given(scenarios(), st.randoms())
def test_the_plan_does_not_depend_on_input_order(
    scenario, rnd: random.Random
):  # inv. 14
    jobs, techs, travel = scenario
    first = run(jobs, techs, distance=StubDistance(travel))
    shuffled_jobs, shuffled_techs = list(jobs), list(techs)
    rnd.shuffle(shuffled_jobs)
    rnd.shuffle(shuffled_techs)
    assert run(shuffled_jobs, shuffled_techs, distance=StubDistance(travel)) == first
    assert run(jobs, techs, distance=StubDistance(travel)) == first


@given(scenarios())
def test_a_normal_job_is_never_given_to_a_technician_at_the_limit(scenario):  # ADR-022
    jobs, techs, travel = scenario
    config = make_config()
    plan = run(jobs, techs, config, StubDistance(travel))
    urgent_ids = {j.id for j in jobs if j.is_urgent}
    load = {t.id: t.assigned_count for t in techs}
    for a in plan.assignments:  # in the order they were planned
        if a.job_id not in urgent_ids:
            assert load[a.technician_id] < config.max_jobs_per_tech_per_day
        load[a.technician_id] += 1


@given(scenarios())
def test_every_result_carries_its_reason(scenario):
    jobs, techs, travel = scenario
    plan = run(jobs, techs, distance=StubDistance(travel))
    for a in plan.assignments:
        assert a.explanation.reasons[0].code == ReasonCode.ASSIGNED
    for u in plan.unassigned:
        assert u.explanation.reasons[0].code == ReasonCode.NO_FEASIBLE_TECHNICIAN
