"""POST /schedule/generate/: who may call it, what it validates, what it returns."""

import datetime

import pytest

from api.models import Job, JobStatus, Skill

from .conftest import client_for, make_job, technician_of

URL = "/api/schedule/generate/"


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(0, 1), datetime.time(23, 59)
    org_a.save()
    return org_a


@pytest.fixture
def tech(org, technician_a):
    technician = technician_of(technician_a)
    technician.skills.add(Skill.objects.get(name="HVAC"))
    technician.shift_start, technician.shift_end = (
        datetime.time(0, 1),
        datetime.time(23, 59),
    )
    technician.save()
    return technician


def today(org):
    from api.services.jobs import local_date

    return local_date(None, org.timezone)


def test_a_dispatcher_plans_the_day_and_gets_the_reasons_back(org, tech, dispatcher_a):
    job = make_job(
        org, is_urgent=True, slot_start=None, slot_end=None, scheduled_date=today(org)
    )
    response = client_for(dispatcher_a).post(URL, {}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["plan_date"] == str(today(org))
    (planned,) = body["assigned"]
    assert planned["job_id"] == job.pk and planned["technician_id"] == tech.pk
    assert planned["reasons"][0]["code"] == "assigned"
    assert "was chosen for" in planned["sentence"]
    assert body["unassigned"] == [] and body["skipped"] == []
    assert Job.objects.get(pk=job.pk).status == JobStatus.ASSIGNED


def test_unassigned_and_skipped_jobs_are_reported(org, tech, dispatcher_a):
    other = Skill.objects.exclude(name="HVAC").first()
    nobody = make_job(
        org,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        scheduled_date=today(org),
        skills=[other],
    )
    nowhere = make_job(
        org,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        scheduled_date=today(org),
        geocode_status="failed",
        lat=None,
        lng=None,
    )
    body = client_for(dispatcher_a).post(URL, {}, format="json").json()
    assert [u["job_id"] for u in body["unassigned"]] == [nobody.pk]
    assert body["unassigned"][0]["reasons"][0]["code"] == "no_feasible_technician"
    assert [(s["job_id"], s["code"]) for s in body["skipped"]] == [
        (nowhere.pk, "needs_location")
    ]


def test_an_unconfigured_organization_gets_a_clear_409(org_a, dispatcher_a):
    response = client_for(dispatcher_a).post(URL, {}, format="json")
    assert response.status_code == 409
    assert response.data["detail"].code == "organization_not_configured"


def test_a_past_day_is_refused(org, dispatcher_a):
    yesterday = today(org) - datetime.timedelta(days=1)
    response = client_for(dispatcher_a).post(
        URL, {"date": str(yesterday)}, format="json"
    )
    assert response.status_code == 400 and "date" in response.json()


def test_a_day_too_far_ahead_is_refused(org, dispatcher_a):
    far = today(org) + datetime.timedelta(days=8)
    response = client_for(dispatcher_a).post(URL, {"date": str(far)}, format="json")
    assert response.status_code == 400


def test_a_garbled_date_is_refused(org, dispatcher_a):
    assert (
        client_for(dispatcher_a).post(URL, {"date": "soon"}, format="json").status_code
        == 400
    )


def test_a_later_day_can_be_planned(org, tech, dispatcher_a):
    tomorrow = today(org) + datetime.timedelta(days=1)
    job = make_job(
        org, is_urgent=True, slot_start=None, slot_end=None, scheduled_date=tomorrow
    )
    body = (
        client_for(dispatcher_a)
        .post(URL, {"date": str(tomorrow)}, format="json")
        .json()
    )
    assert body["plan_date"] == str(tomorrow)
    assert [p["job_id"] for p in body["assigned"]] == [job.pk]


def test_only_jobs_in_my_organization_are_planned(org, tech, dispatcher_a, org_b):
    theirs = make_job(
        org_b, is_urgent=True, slot_start=None, slot_end=None, scheduled_date=today(org)
    )
    client_for(dispatcher_a).post(URL, {}, format="json")
    assert Job.objects.get(pk=theirs.pk).status == JobStatus.UNASSIGNED
