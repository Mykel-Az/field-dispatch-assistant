"""The daily job limit (ADR-022) and the stored plan explanation."""

import pytest

from api.models import Job, JobStatus, Skill
from api.services.jobs import transition

from .conftest import client_for


# ---- the organization setting -----------------------------------------------
def test_the_limit_defaults_to_three(head_a):
    body = client_for(head_a).get("/api/organization/").json()
    assert body["max_jobs_per_tech_per_day"] == 3


def test_the_head_dispatcher_can_change_it(head_a, org_a):
    response = client_for(head_a).patch(
        "/api/organization/",
        {"version": 1, "max_jobs_per_tech_per_day": 5},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["max_jobs_per_tech_per_day"] == 5
    org_a.refresh_from_db()
    assert org_a.max_jobs_per_tech_per_day == 5


def test_a_dispatcher_cannot_change_it(dispatcher_a):
    response = client_for(dispatcher_a).patch(
        "/api/organization/",
        {"version": 1, "max_jobs_per_tech_per_day": 5},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.parametrize("bad", [0, -1, 21, "many"])
def test_the_limit_must_be_between_one_and_twenty(head_a, bad):
    response = client_for(head_a).patch(
        "/api/organization/",
        {"version": 1, "max_jobs_per_tech_per_day": bad},
        format="json",
    )
    assert response.status_code == 400
    assert "max_jobs_per_tech_per_day" in response.json()


# ---- the stored explanation -------------------------------------------------
@pytest.fixture
def assigned_job(org_a, technician_a):
    job = Job.objects.create(
        organization=org_a,
        title="AC not cooling",
        customer_name="Pat",
        customer_phone="5125550100",
        category="hvac",
        is_urgent=True,
        lat=30.3,
        lng=-97.7,
        geocode_status="ok",
    )
    job.acceptable_skills.add(Skill.objects.create(name="Cooling"))
    return transition(
        job,
        JobStatus.ASSIGNED,
        technician_a,
        technician=technician_a.technician_profile,
    )


def test_a_plan_explanation_is_stored_and_survives_other_changes(assigned_job):
    Job.objects.filter(pk=assigned_job.pk).update(
        plan_explanation={"reasons": [{"code": "assigned"}]}
    )
    assert (
        Job.objects.get(pk=assigned_job.pk).plan_explanation["reasons"][0]["code"]
        == "assigned"
    )


@pytest.mark.parametrize("to", [JobStatus.UNASSIGNED, JobStatus.CANCELED])
def test_going_back_to_the_queue_or_canceled_clears_the_explanation(
    assigned_job, technician_a, to
):
    Job.objects.filter(pk=assigned_job.pk).update(plan_explanation={"reasons": []})
    job = Job.objects.get(pk=assigned_job.pk)
    result = transition(job, to, technician_a, reason="test")
    assert result.plan_explanation is None
