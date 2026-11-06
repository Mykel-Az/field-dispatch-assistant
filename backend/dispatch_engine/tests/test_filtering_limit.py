"""FILTER: the daily job limit applies to normal jobs only (ADR-022)."""

from dispatch_engine.filtering import filter_technicians
from dispatch_engine.types import ReasonCode

from .builders import NOW, StubDistance, make_job, make_tech


def run(job, techs, limit):
    return filter_technicians(job, techs, StubDistance(0), NOW, daily_limit=limit)


def test_a_normal_job_rejects_a_technician_at_the_limit():
    result = run(make_job(), [make_tech(id=1, assigned_count=3)], limit=3)
    assert result.feasible == ()
    (rejection,) = result.rejected
    assert rejection.reason.code == ReasonCode.DAILY_LIMIT
    assert rejection.reason.facts == {
        "technician_id": 1,
        "assigned_count": 3,
        "limit": 3,
    }


def test_a_normal_job_accepts_a_technician_under_the_limit():
    result = run(make_job(), [make_tech(id=1, assigned_count=2)], limit=3)
    assert [c.technician_id for c in result.feasible] == [1]


def test_an_urgent_job_ignores_the_limit():
    urgent = make_job(is_urgent=True, slot_start=None, slot_end=None)
    result = run(urgent, [make_tech(id=1, assigned_count=9)], limit=3)
    assert [c.technician_id for c in result.feasible] == [1]


def test_no_limit_means_no_rejection():
    result = run(make_job(), [make_tech(id=1, assigned_count=99)], limit=None)
    assert [c.technician_id for c in result.feasible] == [1]


def test_skill_and_availability_are_reported_before_the_limit():
    result = run(
        make_job(),
        [
            make_tech(id=1, is_available=False, assigned_count=3),
            make_tech(id=2, skill_ids=frozenset({99}), assigned_count=3),
        ],
        limit=3,
    )
    assert [r.reason.code for r in result.rejected] == [
        ReasonCode.UNAVAILABLE,
        ReasonCode.SKILL_MISMATCH,
    ]
