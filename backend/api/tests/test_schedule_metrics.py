"""GET /schedule/metrics/: the plan next to a round-robin baseline (ADR-030)."""

import datetime

import pytest
from rest_framework.test import APIClient

from api.models import Job, JobStatus, Skill

from .conftest import Role, client_for, make_job, make_user, technician_of

DAY = datetime.date(2026, 11, 2)
URL = f"/api/schedule/metrics/?date={DAY.isoformat()}"
UTC = datetime.UTC


def at(hour):
    return datetime.datetime(2026, 11, 2, hour, tzinfo=UTC)


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.0, -97.0
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


@pytest.fixture
def north_tech(org):
    tech = technician_of(make_user(org, Role.TECHNICIAN, "n@x.example"))
    tech.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    return tech


@pytest.fixture
def south_tech(org):
    tech = technician_of(make_user(org, Role.TECHNICIAN, "s@x.example"))
    tech.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    return tech


def placed(org, tech, position, lat, **fields):
    return make_job(
        org,
        status=JobStatus.ASSIGNED,
        technician=tech,
        sequence_position=position,
        lat=lat,
        lng=-97.0,
        slot_start=at(15),
        slot_end=at(23),
        scheduled_date=DAY,
        **fields,
    )


def test_an_empty_day_is_all_zeros(org, dispatcher_a):
    body = client_for(dispatcher_a).get(URL).json()
    assert body["jobs"] == 0 and body["in_queue"] == 0
    assert body["plan"]["travel_miles"] == 0 and body["baseline"]["sla_breaches"] == 0


def test_the_plan_drives_less_than_the_baseline_on_the_same_jobs(
    org, dispatcher_a, north_tech, south_tech
):
    """Hand-computed (1 degree of latitude = 69.09 miles, workstation at 30.0).

    The plan keeps each technician on their own side: 34.5 + 6.9 miles each, 82.8 in all.
    The baseline deals jobs 1..4 alternately, so each technician crosses town:
    north 34.5 + 69.1, south 41.5 + 82.9, 228 in all.
    """
    placed(org, north_tech, 1, 30.5)  # job 1
    placed(org, north_tech, 2, 30.6)  # job 2
    placed(org, south_tech, 1, 29.5)  # job 3
    placed(org, south_tech, 2, 29.4)  # job 4
    body = client_for(dispatcher_a).get(URL).json()
    assert body["plan"]["jobs"] == body["baseline"]["jobs"] == 4  # the same work
    assert body["plan"]["travel_miles"] == pytest.approx(82.8, abs=0.5)
    assert body["baseline"]["travel_miles"] == pytest.approx(228.0, abs=2.0)


def test_a_job_only_the_other_skill_can_do_is_unplaced_in_the_baseline(
    org, dispatcher_a, north_tech
):
    plumbing = Skill.objects.exclude(name="Heating & Air Conditioning").first()
    placed(org, north_tech, 1, 30.1, skills=[plumbing])
    body = client_for(dispatcher_a).get(URL).json()
    assert body["plan"]["jobs"] == 1  # a person put it there
    assert body["baseline"]["jobs"] == 0 and body["baseline"]["unplaced"] == 1


def test_jobs_nobody_has_taken_are_counted_apart(org, dispatcher_a, north_tech):
    placed(org, north_tech, 1, 30.1)
    make_job(org, lat=30.2, lng=-97.0, scheduled_date=DAY)
    body = client_for(dispatcher_a).get(URL).json()
    assert body["jobs"] == 1 and body["in_queue"] == 1


def test_workload_spread_is_reported_for_both(
    org, dispatcher_a, north_tech, south_tech
):
    for n in (1, 2, 3):
        placed(org, north_tech, n, 30.0 + n / 100)
    body = client_for(dispatcher_a).get(URL).json()
    assert body["plan"]["workload_spread"] == 3
    assert body["baseline"]["workload_spread"] <= 1  # dealt evenly


def test_another_organizations_jobs_are_not_in_the_numbers(
    org, dispatcher_a, org_b, technician_b, north_tech
):
    foreign = technician_of(technician_b)
    make_job(
        org_b,
        status=JobStatus.ASSIGNED,
        technician=foreign,
        sequence_position=1,
        scheduled_date=DAY,
    )
    assert Job.objects.filter(organization=org_b).count() == 1
    assert client_for(dispatcher_a).get(URL).json()["jobs"] == 0


def test_a_technician_cannot_read_it(org, technician_a):
    assert client_for(technician_a).get(URL).status_code == 403


def test_anonymous_is_refused(org):
    assert APIClient().get(URL).status_code in (401, 403)


def test_it_changes_nothing(org, dispatcher_a, north_tech):
    job = placed(org, north_tech, 1, 30.1)
    before = Job.objects.filter(pk=job.pk).values().get()
    client_for(dispatcher_a).get(URL)
    assert Job.objects.filter(pk=job.pk).values().get() == before
