"""Adapters: Django rows become engine views, and nothing private crosses over (ADR-019)."""

import dataclasses
import datetime
from zoneinfo import ZoneInfo

import pytest

from api.adapters import (
    JobNotLocated,
    OrganizationNotConfigured,
    job_to_view,
    org_to_config,
    technician_to_view,
)
from api.models import Job, JobStatus, Skill

from .conftest import Role, make_user

DAY = datetime.date(2026, 11, 3)
UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 3, 14, 0, tzinfo=UTC)  # 8:00 in Chicago (CST)


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


@pytest.fixture
def skill(db):
    return Skill.objects.create(name="Refrigeration")


def make_job(org, skill, **fields):
    fields.setdefault("title", "AC not cooling")
    fields.setdefault("customer_name", "Pat Customer")
    fields.setdefault("customer_phone", "5125550100")
    fields.setdefault("category", "hvac")
    fields.setdefault("is_urgent", True)
    fields.setdefault("lat", 30.30)
    fields.setdefault("lng", -97.70)
    fields.setdefault("geocode_status", "ok")
    fields.setdefault("address", "1 Private Lane")
    job = Job.objects.create(organization=org, **fields)
    job.acceptable_skills.add(skill)
    return job


# ---- organization -----------------------------------------------------------
def test_org_config_uses_the_workstation_and_strategy(org):
    org.scoring_strategy = "nearest"
    config = org_to_config(org)
    assert (config.workstation.lat, config.workstation.lng) == (30.27, -97.74)
    assert config.scoring_strategy == "nearest"


def test_org_config_carries_the_organizations_daily_limit(org):
    org.max_jobs_per_tech_per_day = 5
    assert org_to_config(org).max_jobs_per_tech_per_day == 5


def test_an_unconfigured_organization_cannot_be_planned(org_a):
    with pytest.raises(OrganizationNotConfigured):
        org_to_config(org_a)


# ---- jobs -------------------------------------------------------------------
def test_job_view_carries_title_location_skills_and_duration(org, skill):
    job = make_job(org, skill, estimated_duration_minutes=45)
    view = job_to_view(job)
    assert (view.id, view.label, view.duration_minutes) == (
        job.pk,
        "AC not cooling",
        45,
    )
    assert (view.location.lat, view.location.lng) == (30.30, -97.70)
    assert view.acceptable_skill_ids == {skill.pk}
    assert view.is_urgent and view.slot_start is None


def test_job_view_keeps_the_agreed_window(org, skill):
    start = NOW + datetime.timedelta(hours=2)
    job = make_job(
        org,
        skill,
        is_urgent=False,
        slot_start=start,
        slot_end=start + datetime.timedelta(hours=2),
    )
    view = job_to_view(job)
    assert (view.slot_start, view.slot_end) == (job.slot_start, job.slot_end)


def test_the_engine_never_sees_customer_details(org, skill):
    """ADR-019: no customer name, phone or address in engine types."""
    job = make_job(org, skill)
    dumped = repr(dataclasses.asdict(job_to_view(job)))
    for secret in ("Pat Customer", "5125550100", "1 Private Lane"):
        assert secret not in dumped


def test_a_job_without_coordinates_is_refused(org, skill):
    job = make_job(org, skill, lat=None, lng=None, geocode_status="failed")
    with pytest.raises(JobNotLocated):
        job_to_view(job)


# ---- technicians ------------------------------------------------------------
def tech_of(org, skill, **user_fields):
    user = make_user(org, Role.TECHNICIAN, "tech@example.com", **user_fields)
    technician = user.technician_profile
    technician.skills.add(skill)
    return technician


def view_of(technician, org, workload=(), now=NOW):
    return technician_to_view(
        technician, plan_date=DAY, organization=org, workload=workload, now=now
    )


def test_shift_times_are_read_on_the_organizations_clock(org, skill):
    view = view_of(tech_of(org, skill), org)
    chicago = ZoneInfo("America/Chicago")
    assert view.shift_start == datetime.datetime(2026, 11, 3, 8, tzinfo=chicago)
    assert view.shift_end == datetime.datetime(2026, 11, 3, 17, tzinfo=chicago)
    assert view.shift_start.utcoffset() is not None


def test_a_free_technician_starts_at_the_workstation_now(org, skill):
    view = view_of(tech_of(org, skill), org)
    assert view.free_at == NOW
    assert (view.position.lat, view.position.lng) == (30.27, -97.74)
    assert view.assigned_count == 0
    assert view.skill_ids == {skill.pk}


def test_an_inactive_user_is_unavailable(org, skill):
    technician = tech_of(org, skill)
    technician.user.is_active = False
    assert view_of(technician, org).is_available is False


def test_an_ongoing_job_holds_the_technician_until_it_ends(org, skill):
    technician = tech_of(org, skill)
    job = make_job(
        org,
        skill,
        status=JobStatus.ONGOING,
        technician=technician,
        arrived_at=NOW,
        estimated_duration_minutes=90,
        lat=30.50,
        lng=-97.60,
    )
    view = view_of(technician, org, [job])
    assert view.free_at == NOW + datetime.timedelta(minutes=90)
    assert (view.position.lat, view.position.lng) == (30.50, -97.60)
    assert view.assigned_count == 1


def test_an_assigned_job_ends_after_its_estimated_arrival(org, skill):
    technician = tech_of(org, skill)
    arrival = NOW + datetime.timedelta(hours=1)
    job = make_job(
        org,
        skill,
        status=JobStatus.ASSIGNED,
        technician=technician,
        estimated_arrival=arrival,
        estimated_duration_minutes=60,
        scheduled_date=DAY,
    )
    assert view_of(technician, org, [job]).free_at == arrival + datetime.timedelta(
        hours=1
    )


def test_the_latest_ending_job_decides_where_the_technician_is(org, skill):
    technician = tech_of(org, skill)
    early = make_job(
        org,
        skill,
        status=JobStatus.ASSIGNED,
        technician=technician,
        sequence_position=1,
        estimated_arrival=NOW,
        estimated_duration_minutes=30,
        lat=30.31,
        lng=-97.71,
    )
    late = make_job(
        org,
        skill,
        status=JobStatus.ASSIGNED,
        technician=technician,
        sequence_position=2,
        estimated_arrival=NOW + datetime.timedelta(hours=2),
        estimated_duration_minutes=30,
        lat=30.40,
        lng=-97.60,
    )
    view = view_of(technician, org, [early, late])
    assert view.free_at == NOW + datetime.timedelta(hours=2, minutes=30)
    assert (view.position.lat, view.position.lng) == (30.40, -97.60)
    assert view.assigned_count == 2


def test_a_job_that_ended_in_the_past_does_not_hold_the_technician(org, skill):
    technician = tech_of(org, skill)
    job = make_job(
        org,
        skill,
        status=JobStatus.ASSIGNED,
        technician=technician,
        estimated_arrival=NOW - datetime.timedelta(hours=5),
        estimated_duration_minutes=30,
    )
    view = view_of(technician, org, [job])
    assert view.free_at == NOW  # it still counts toward the daily load
    assert view.assigned_count == 1
