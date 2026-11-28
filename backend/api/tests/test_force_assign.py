"""Force-assign an urgent job, bumping what stands in the way (ADR-029)."""

import datetime

import pytest

from api.models import Job, JobStatus, JobStatusHistory, Skill
from api.services import jobs as job_service
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import client_for, make_job, technician_of

UTC = datetime.UTC
NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago (CST)
DAY = datetime.date(2026, 11, 2)
CLOCK = FixedClock(NOW)


def at(hour, minute=0):
    return datetime.datetime(2026, 11, 2, hour, minute, tzinfo=UTC)


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


@pytest.fixture
def tech(org, technician_a):
    technician = technician_of(technician_a)
    technician.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    return technician


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(scheduling, "SystemClock", lambda: CLOCK)


def job(org, **fields):
    fields.setdefault("slot_start", at(18))
    fields.setdefault("slot_end", at(20))
    fields.setdefault("scheduled_date", DAY)
    fields.setdefault("lat", 30.30)
    fields.setdefault("lng", -97.70)
    made = make_job(org, **fields)
    Job.objects.filter(pk=made.pk).update(created_at=NOW)
    return Job.objects.get(pk=made.pk)


def urgent(org, **fields):
    return job(
        org,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        estimated_duration_minutes=45,
        **fields,
    )


def held(org, tech, *, start, minutes, position, **fields):
    """A job already assigned to the technician, planned to start at `start`."""
    return job(
        org,
        status=JobStatus.ASSIGNED,
        technician=tech,
        sequence_position=position,
        estimated_arrival=start,
        estimated_duration_minutes=minutes,
        slot_start=start,
        slot_end=start + datetime.timedelta(hours=3),
        **fields,
    )


def force(j, tech, actor, **kwargs):
    return scheduling.force_assign(
        job=j, technician=tech, actor=actor, client_version=j.version, **kwargs
    )


def fresh(j):
    return Job.objects.get(pk=j.pk)


# ---- no bump needed ---------------------------------------------------------------
def test_a_free_technician_takes_the_urgent_job_and_nobody_is_bumped(
    org, dispatcher_a, tech
):
    j = urgent(org)
    result = force(j, tech, dispatcher_a)
    assert result.bumped_job_ids == [] and result.sla_label == "ok"
    saved = fresh(j)
    assert (saved.status, saved.technician_id) == (JobStatus.ASSIGNED, tech.pk)
    assert saved.sequence_position == 1
    assert "forced_assign" in [r["code"] for r in saved.plan_explanation["reasons"]]


def test_the_history_row_says_it_was_forced(org, dispatcher_a, tech):
    j = urgent(org)
    force(j, tech, dispatcher_a)
    row = JobStatusHistory.objects.filter(job=j, to_status="assigned").get()
    assert row.changed_by_id == dispatcher_a.pk and "Forced" in row.reason


# ---- bumping ----------------------------------------------------------------------
def test_the_lowest_priority_job_in_the_way_is_bumped_and_the_other_stays(
    org, dispatcher_a, tech
):
    low = held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    high = held(org, tech, start=at(17), minutes=60, position=2, priority="high")
    j = urgent(org)
    result = force(j, tech, dispatcher_a)
    assert result.bumped_job_ids == [low.pk] and result.sla_label != "breach"
    assert (
        fresh(low).status == JobStatus.UNASSIGNED and fresh(low).technician_id is None
    )
    assert fresh(high).status == JobStatus.ASSIGNED
    assert fresh(high).technician_id == tech.pk
    assert fresh(high).estimated_arrival == at(17)  # untouched time (invariant 12)


def test_the_bumped_job_has_a_history_row_naming_the_urgent_job(
    org, dispatcher_a, tech
):
    low = held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    j = urgent(org)
    force(j, tech, dispatcher_a)
    row = JobStatusHistory.objects.filter(job=low, to_status="unassigned").get()
    assert f"#{j.pk}" in row.reason


def test_stop_numbers_are_one_to_n_in_time_order_afterwards(org, dispatcher_a, tech):
    held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    held(org, tech, start=at(17), minutes=60, position=2, priority="high")
    j = urgent(org)
    force(j, tech, dispatcher_a)
    day = Job.objects.filter(technician=tech, scheduled_date=DAY).order_by(
        "sequence_position"
    )
    assert [x.sequence_position for x in day] == [1, 2]
    assert day[0].pk == j.pk  # the urgent job runs first


def test_a_job_that_does_not_help_is_not_bumped(org, dispatcher_a, tech):
    """The blocker is a high-priority job at 15:00; the low one is later and irrelevant."""
    block = held(org, tech, start=at(15), minutes=180, position=1, priority="high")
    later = held(org, tech, start=at(19), minutes=60, position=2, priority="low")
    j = urgent(org)
    result = force(j, tech, dispatcher_a)
    assert result.bumped_job_ids == [block.pk]
    assert fresh(later).status == JobStatus.ASSIGNED


def test_an_ongoing_job_is_never_bumped_and_the_urgent_job_is_assigned_late(
    org, dispatcher_a, tech
):
    ongoing = job(
        org,
        status=JobStatus.ONGOING,
        technician=tech,
        sequence_position=1,
        estimated_arrival=at(15),
        arrived_at=at(15),
        estimated_duration_minutes=300,
        slot_start=at(15),
        slot_end=at(18),
    )
    j = urgent(org)
    result = force(j, tech, dispatcher_a)  # nothing to bump: expected, not an error
    assert result.bumped_job_ids == [] and result.sla_label == "breach"
    assert fresh(ongoing).status == JobStatus.ONGOING
    assert fresh(j).status == JobStatus.ASSIGNED


def test_another_urgent_job_is_never_bumped(org, dispatcher_a, tech):
    other = job(
        org,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        status=JobStatus.ASSIGNED,
        technician=tech,
        sequence_position=1,
        estimated_arrival=at(15),
        estimated_duration_minutes=300,
    )
    j = urgent(org)
    result = force(j, tech, dispatcher_a)
    assert result.bumped_job_ids == []
    assert fresh(other).status == JobStatus.ASSIGNED


# ---- dry run ---------------------------------------------------------------------
def test_a_dry_run_reports_the_bump_and_writes_nothing(org, dispatcher_a, tech):
    low = held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    j = urgent(org)
    before = JobStatusHistory.objects.count()
    result = force(j, tech, dispatcher_a, dry_run=True)
    assert result.bumped_job_ids == [low.pk] and result.dry_run
    assert fresh(j).status == JobStatus.UNASSIGNED
    assert fresh(low).status == JobStatus.ASSIGNED
    assert JobStatusHistory.objects.count() == before


# ---- refusals --------------------------------------------------------------------
def test_a_normal_job_cannot_be_force_assigned(org, dispatcher_a, tech):
    j = job(org)
    with pytest.raises(scheduling.JobNotUrgent):
        force(j, tech, dispatcher_a)


def test_an_already_assigned_job_cannot_be_force_assigned(org, dispatcher_a, tech):
    j = urgent(org)
    job_service.transition(fresh(j), "assigned", dispatcher_a, technician=tech)
    with pytest.raises(job_service.IllegalJobTransition):
        force(fresh(j), tech, dispatcher_a)


def test_a_stale_version_is_refused(org, dispatcher_a, tech):
    j = urgent(org)
    with pytest.raises(Exception) as caught:
        scheduling.force_assign(
            job=j, technician=tech, actor=dispatcher_a, client_version=j.version + 5
        )
    assert getattr(caught.value, "detail", None) is not None
    assert fresh(j).status == JobStatus.UNASSIGNED


# ---- the endpoint ----------------------------------------------------------------
def url(j):
    return f"/api/jobs/{j.pk}/force-assign/"


def test_the_endpoint_returns_the_result(org, dispatcher_a, tech):
    low = held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    j = urgent(org)
    response = client_for(dispatcher_a).post(
        url(j), {"technician_id": tech.pk, "version": j.version}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bumped_job_ids"] == [low.pk] and body["dry_run"] is False
    assert body["job"]["status"] == "assigned"


def test_the_endpoint_dry_run_changes_nothing(org, dispatcher_a, tech):
    held(org, tech, start=at(15), minutes=120, position=1, priority="low")
    j = urgent(org)
    response = client_for(dispatcher_a).post(
        url(j),
        {"technician_id": tech.pk, "version": j.version, "dry_run": True},
        format="json",
    )
    assert response.status_code == 200 and response.json()["dry_run"] is True
    assert fresh(j).status == JobStatus.UNASSIGNED


def test_a_normal_job_is_409_not_urgent(org, dispatcher_a, tech):
    j = job(org)
    response = client_for(dispatcher_a).post(
        url(j), {"technician_id": tech.pk, "version": j.version}, format="json"
    )
    assert response.status_code == 409
    assert response.data["detail"].code == "not_urgent"


def test_a_technician_cannot_force_assign(org, technician_a, tech):
    j = urgent(org)
    response = client_for(technician_a).post(
        url(j), {"technician_id": tech.pk, "version": j.version}, format="json"
    )
    assert response.status_code == 403


def test_anonymous_gets_401(org, tech):
    from rest_framework.test import APIClient

    j = urgent(org)
    response = APIClient().post(
        url(j), {"technician_id": tech.pk, "version": j.version}, format="json"
    )
    assert response.status_code in (401, 403)


def test_another_organizations_job_is_404(org, dispatcher_a, org_b, tech):
    other = make_job(org_b, is_urgent=True, slot_start=None, slot_end=None)
    response = client_for(dispatcher_a).post(
        url(other), {"technician_id": tech.pk, "version": other.version}, format="json"
    )
    assert response.status_code == 404


def test_another_organizations_technician_is_rejected(
    org, dispatcher_a, org_b, technician_b
):
    j = urgent(org)
    foreign = technician_of(technician_b)
    response = client_for(dispatcher_a).post(
        url(j), {"technician_id": foreign.pk, "version": j.version}, format="json"
    )
    assert response.status_code == 400
    assert fresh(j).status == JobStatus.UNASSIGNED
