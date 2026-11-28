"""Minor jobs also accept helper skills; major jobs need the specialist (ADR-034)."""

import datetime

import pytest

from api.models import CandidateSkillRule, Job, JobCategory, Skill
from api.services import jobs as job_service
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import client_for, make_job, technician_of
from .test_jobs_api import body

UTC = datetime.UTC
NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago
DAY = datetime.date(2026, 11, 2)

HANDY = "Contractors & Handymen"
ELECTRIC = "Electricians"
APPLIANCE = "Appliances and Repair"


def names(skills):
    return [s.name for s in skills]


# ---- the rules --------------------------------------------------------------
def test_a_major_job_needs_the_specialist_only(db):
    assert names(job_service.default_skills_for("electrical", "major")) == [ELECTRIC]


def test_a_minor_job_also_accepts_the_helpers(db):
    minor = names(job_service.default_skills_for("electrical", "minor"))
    assert set(minor) == {ELECTRIC, HANDY, APPLIANCE}
    assert len(minor) == 3  # the specialist is not listed twice


def test_the_default_is_major(db):
    assert names(job_service.default_skills_for("electrical")) == [ELECTRIC]


def test_a_category_without_helpers_is_the_same_minor_or_major(db):
    assert names(job_service.default_skills_for("cleaning", "minor")) == [
        "Home Cleaning"
    ]
    assert names(job_service.default_skills_for("cleaning", "major")) == [
        "Home Cleaning"
    ]


def test_helpers_are_never_in_the_major_list(db):
    helpers = CandidateSkillRule.objects.filter(minor_only=True)
    assert helpers.exists()
    for rule in helpers:
        assert rule.skill.name not in names(
            job_service.default_skills_for(rule.category, "major")
        )


def test_there_are_fifteen_categories_and_fifteen_skills(db):
    assert len(JobCategory.choices) == 15
    assert Skill.objects.count() == 15


# ---- creating and reading ---------------------------------------------------
def test_create_a_minor_electrical_job_gets_the_helper_skills(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(category="electrical", complexity="minor"), format="json"
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["complexity"] == "minor"
    assert {s["name"] for s in data["acceptable_skills"]} == {
        ELECTRIC,
        HANDY,
        APPLIANCE,
    }


def test_create_without_complexity_is_major_and_specialist_only(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(category="electrical"), format="json"
    )
    data = response.json()
    assert data["complexity"] == "major"
    assert [s["name"] for s in data["acceptable_skills"]] == [ELECTRIC]


def test_an_unknown_complexity_is_refused(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(complexity="huge"), format="json"
    )
    assert response.status_code == 400


def test_chosen_skills_win_over_the_defaults(dispatcher_a):
    only_handy = Skill.objects.get(name=HANDY).pk
    response = client_for(dispatcher_a).post(
        "/api/jobs/",
        body(category="electrical", complexity="minor", skill_ids=[only_handy]),
        format="json",
    )
    assert [s["name"] for s in response.json()["acceptable_skills"]] == [HANDY]


def test_complexity_is_in_the_list_and_can_be_edited(dispatcher_a, org_a):
    job = make_job(org_a)
    client = client_for(dispatcher_a)
    assert client.get("/api/jobs/").json()["results"][0]["complexity"] == "major"
    response = client.patch(
        f"/api/jobs/{job.pk}/", {"version": 1, "complexity": "minor"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert Job.objects.get(pk=job.pk).complexity == "minor"


# ---- the categories endpoint -------------------------------------------------
def test_categories_endpoint_lists_all_with_skill_ids(dispatcher_a):
    response = client_for(dispatcher_a).get("/api/job-categories/")
    assert response.status_code == 200
    rows = {r["value"]: r for r in response.json()}
    assert len(rows) == 15
    electrician = Skill.objects.get(name=ELECTRIC).pk
    handyman = Skill.objects.get(name=HANDY).pk
    assert rows["electrical"]["label"] == "Electricians"
    assert rows["electrical"]["major_skill_ids"] == [electrician]
    assert set(rows["electrical"]["minor_skill_ids"]) >= {electrician, handyman}
    assert handyman not in rows["electrical"]["major_skill_ids"]


def test_categories_endpoint_is_for_dispatchers(technician_a):
    assert client_for(technician_a).get("/api/job-categories/").status_code == 403


# ---- the planner honours it --------------------------------------------------
@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.30, -97.70
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


def plan(org, actor):
    return scheduling.generate_schedule(
        organization=org, actor=actor, plan_date=DAY, clock=FixedClock(NOW)
    )


def electrical_job(org, complexity):
    skills = job_service.default_skills_for("electrical", complexity)
    made = make_job(
        org,
        category="electrical",
        complexity=complexity,
        skills=skills,
        scheduled_date=DAY,
        lat=30.30,
        lng=-97.70,
        slot_start=NOW + datetime.timedelta(hours=3),
        slot_end=NOW + datetime.timedelta(hours=5),
    )
    return made


def test_a_handyman_gets_the_minor_electrical_job_and_not_the_major_one(
    org, dispatcher_a, technician_a
):
    handyman = technician_of(technician_a)
    handyman.skills.set([Skill.objects.get(name=HANDY)])
    minor = electrical_job(org, "minor")
    major = electrical_job(org, "major")
    plan(org, dispatcher_a)
    minor.refresh_from_db()
    major.refresh_from_db()
    assert minor.technician_id == handyman.pk
    assert major.technician_id is None


def test_an_electrician_gets_both(org, dispatcher_a, technician_a):
    electrician = technician_of(technician_a)
    electrician.skills.set([Skill.objects.get(name=ELECTRIC)])
    minor = electrical_job(org, "minor")
    major = electrical_job(org, "major")
    plan(org, dispatcher_a)
    minor.refresh_from_db()
    major.refresh_from_db()
    assert minor.technician_id == electrician.pk
    assert major.technician_id == electrician.pk
