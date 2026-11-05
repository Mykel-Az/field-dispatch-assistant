"""
The engine's input and output types: they accept good data and refuse bad data loudly.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from dispatch_engine.types import (
    Assignment,
    Explanation,
    JobView,
    Location,
    OrgConfig,
    Plan,
    Priority,
    Reason,
    ReasonCode,
    SlaLabel,
    TechView,
    Unassigned,
)

# A fixed moment, not datetime.now(): tests must give the same result on every run.
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
NAIVE = datetime(2026, 11, 3, 9, 0)  # noqa: DTZ001  (on purpose: no time zone)
AUSTIN = Location(30.2672, -97.7431)


def make_job(**overrides) -> JobView:
    fields = {
        "id": 1,
        "label": "AC not cooling",
        "location": AUSTIN,
        "is_urgent": False,
        "created_at": NOW,
        "slot_start": NOW + timedelta(hours=1),
        "slot_end": NOW + timedelta(hours=2),
        "duration_minutes": 60,
        "acceptable_skill_ids": frozenset({1, 2}),
    }
    return JobView(**{**fields, **overrides})


def make_tech(**overrides) -> TechView:
    fields = {
        "id": 7,
        "label": "Sam",
        "skill_ids": frozenset({1}),
        "shift_start": NOW,
        "shift_end": NOW + timedelta(hours=8),
        "is_available": True,
        "free_at": NOW,
        "position": AUSTIN,
        "assigned_count": 0,
    }
    return TechView(**{**fields, **overrides})


def make_config(**overrides) -> OrgConfig:
    fields = {
        "workstation": AUSTIN,
        "scoring_strategy": "balanced",
        "speed_mph": 30.0,
        "urgent_buffer_minutes": 60.0,
        "at_risk_minutes": 30.0,
        "max_jobs_per_tech_per_day": 4,
    }
    return OrgConfig(**{**fields, **overrides})


def make_assignment(**overrides) -> Assignment:
    fields = {
        "job_id": 1,
        "technician_id": 7,
        "estimated_arrival": NOW + timedelta(minutes=90),
        "slack_minutes": 30.0,
        "sla_label": SlaLabel.OK,
        "risk": 0.2,
        "explanation": Explanation(()),
    }
    return Assignment(**{**fields, **overrides})


# ---- Location ---------------------------------------------------------------
@pytest.mark.parametrize("lat, lng", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_location_out_of_range_is_refused(lat, lng):
    with pytest.raises(ValueError):
        Location(lat, lng)


@pytest.mark.parametrize("lat, lng", [(90, 180), (-90, -180), (0, 0)])
def test_location_edges_are_allowed(lat, lng):
    assert Location(lat, lng).lat == lat


# ---- JobView ----------------------------------------------------------------
def test_a_valid_job_is_accepted():
    job = make_job()
    assert job.id == 1 and job.location == AUSTIN
    assert job.acceptable_skill_ids == frozenset({1, 2})


def test_an_urgent_job_may_have_no_slot():
    job = make_job(is_urgent=True, slot_start=None, slot_end=None)
    assert job.slot_start is None and job.slot_end is None


def test_a_non_urgent_job_without_a_slot_is_refused():  # invariant 7
    with pytest.raises(ValueError, match="needs a slot"):
        make_job(is_urgent=False, slot_start=None, slot_end=None)


def test_a_half_set_slot_is_refused():
    with pytest.raises(ValueError, match="together"):
        make_job(slot_end=None)


@pytest.mark.parametrize("start_hours, end_hours", [(2, 1), (1, 1)])
def test_a_slot_must_end_after_it_starts(start_hours, end_hours):
    with pytest.raises(ValueError, match="before slot end"):
        make_job(
            slot_start=NOW + timedelta(hours=start_hours),
            slot_end=NOW + timedelta(hours=end_hours),
        )


@pytest.mark.parametrize("field", ["created_at", "slot_start", "slot_end"])
def test_a_job_refuses_naive_datetimes(field):
    with pytest.raises(ValueError, match="timezone-aware"):
        make_job(**{field: NAIVE})


def test_a_job_needs_a_positive_duration():
    with pytest.raises(ValueError, match="duration"):
        make_job(duration_minutes=0)


# ---- TechView ---------------------------------------------------------------
def test_a_valid_technician_is_accepted():
    assert make_tech().is_available is True


def test_a_shift_must_end_after_it_starts():
    with pytest.raises(ValueError, match="before shift end"):
        make_tech(shift_start=NOW + timedelta(hours=8), shift_end=NOW)


@pytest.mark.parametrize("field", ["shift_start", "shift_end", "free_at"])
def test_a_technician_refuses_naive_datetimes(field):
    with pytest.raises(ValueError, match="timezone-aware"):
        make_tech(**{field: NAIVE})


def test_a_technician_cannot_have_a_negative_load():
    with pytest.raises(ValueError, match="negative"):
        make_tech(assigned_count=-1)


# ---- OrgConfig --------------------------------------------------------------
def test_a_valid_config_is_accepted():
    assert make_config().speed_mph == 30.0


@pytest.mark.parametrize("speed", [0, -5])
def test_speed_must_be_positive(speed):  # distance divides by it
    with pytest.raises(ValueError, match="speed"):
        make_config(speed_mph=speed)


def test_minutes_cannot_be_negative():
    with pytest.raises(ValueError, match="negative"):
        make_config(at_risk_minutes=-1)


def test_the_daily_job_target_must_be_at_least_one():
    with pytest.raises(ValueError, match="max_jobs"):
        make_config(max_jobs_per_tech_per_day=0)


# ---- Assignment, Explanation, Plan ------------------------------------------
@pytest.mark.parametrize("risk", [-0.1, 1.1])
def test_risk_stays_between_zero_and_one(risk):
    with pytest.raises(ValueError, match="risk"):
        make_assignment(risk=risk)


def test_an_assignment_refuses_a_naive_arrival():
    with pytest.raises(ValueError, match="timezone-aware"):
        make_assignment(estimated_arrival=NAIVE)


def test_a_plan_holds_assignments_and_unassigned_jobs():
    why = Explanation(
        (Reason(ReasonCode.SKILL_MISMATCH, {"technician_id": 7, "job_id": 2}),)
    )
    plan = Plan((make_assignment(),), (Unassigned(2, why),))
    assert plan.assignments[0].job_id == 1
    assert plan.unassigned[0].explanation.reasons[0].code == "skill_mismatch"


def test_enum_values_are_the_strings_the_api_will_send():
    assert SlaLabel.AT_RISK == "at_risk"
    assert ReasonCode.AFTER_CLOSING == "after_closing"


# ---- immutability (determinism needs inputs that cannot change under the engine)
@pytest.mark.parametrize(
    "obj, field",
    [
        (make_job(), "label"),
        (make_tech(), "is_available"),
        (make_config(), "speed_mph"),
    ],
)
def test_types_are_frozen(obj, field):
    with pytest.raises(FrozenInstanceError):
        setattr(obj, field, "changed")


# ---- priority and movable windows -------------------------------------------
def test_priority_defaults_to_normal_and_the_window_to_fixed():
    job = make_job()
    assert job.priority == Priority.NORMAL
    assert job.slot_is_fixed is True


@pytest.mark.parametrize("priority", [0, 4, -1])
def test_an_unknown_priority_is_refused(priority):
    with pytest.raises(ValueError):
        make_job(priority=priority)


def test_a_movable_window_is_allowed():
    assert make_job(slot_is_fixed=False).slot_is_fixed is False
