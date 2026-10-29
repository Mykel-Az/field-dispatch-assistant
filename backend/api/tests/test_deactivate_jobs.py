"""Deactivating a technician: block on Ongoing, release Assigned (S1-3 step 6)."""

import pytest

from api.models import CustomUser, JobStatusHistory

from .conftest import client_for, make_job, make_user, technician_of


@pytest.fixture
def tech(technician_a):
    return technician_of(technician_a)


def deactivate(head, user):
    return client_for(head).post(f"/api/users/{user.pk}/deactivate/")


def test_ongoing_job_blocks_deactivation(head_a, org_a, technician_a, tech):
    make_job(org_a, status="ongoing", technician=tech)
    response = deactivate(head_a, technician_a)
    assert response.status_code == 409
    assert response.data["detail"].code == "has_ongoing_job"
    assert response.json()["detail"] == (
        "This technician has a job in progress. Finish or reassign it first."
    )
    technician_a.refresh_from_db()
    assert technician_a.is_active


def test_blocked_deactivation_leaves_the_session_alive(
    head_a, org_a, technician_a, tech
):
    make_job(org_a, status="ongoing", technician=tech)
    tech_client = client_for(technician_a)
    deactivate(head_a, technician_a)
    assert tech_client.get("/api/auth/me/").status_code == 200


def test_blocked_deactivation_does_not_release_assigned_jobs(
    head_a, org_a, technician_a, tech
):
    make_job(org_a, status="ongoing", technician=tech)
    waiting = make_job(org_a, status="assigned", technician=tech, sequence_position=2)
    deactivate(head_a, technician_a)
    waiting.refresh_from_db()
    assert (waiting.status, waiting.technician_id) == ("assigned", tech.pk)


def test_assigned_jobs_go_back_to_the_queue(head_a, org_a, technician_a, tech):
    jobs = [
        make_job(org_a, status="assigned", technician=tech, sequence_position=n)
        for n in (1, 2)
    ]
    response = deactivate(head_a, technician_a)
    assert response.status_code == 200 and response.json()["is_active"] is False
    for job in jobs:
        job.refresh_from_db()
        assert (job.status, job.technician_id, job.sequence_position) == (
            "unassigned",
            None,
            None,
        )
        [row] = JobStatusHistory.objects.filter(job=job)
        assert row.reason == "technician deactivated"
        assert row.changed_by == head_a and row.technician_id == tech.pk


def test_other_technicians_jobs_are_untouched(head_a, org_a, technician_a, tech):
    other = technician_of(make_user(org_a, "technician", "other@example.com"))
    theirs = make_job(org_a, status="assigned", technician=other, sequence_position=1)
    deactivate(head_a, technician_a)
    theirs.refresh_from_db()
    assert theirs.status == "assigned"


def test_deactivating_twice_is_idempotent(head_a, org_a, technician_a, tech):
    make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    assert deactivate(head_a, technician_a).status_code == 200
    assert deactivate(head_a, technician_a).status_code == 200
    assert JobStatusHistory.objects.count() == 1


def test_reactivating_does_not_restore_the_jobs(head_a, org_a, technician_a, tech):
    job = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    deactivate(head_a, technician_a)
    client_for(head_a).post(f"/api/users/{technician_a.pk}/reactivate/")
    job.refresh_from_db()
    assert (job.status, job.technician_id) == ("unassigned", None)
    assert CustomUser.objects.get(pk=technician_a.pk).is_active


def test_a_technician_with_no_jobs_still_deactivates(head_a, technician_a):
    assert deactivate(head_a, technician_a).status_code == 200


def test_dispatchers_have_no_job_checks(head_a, dispatcher_a):
    assert deactivate(head_a, dispatcher_a).status_code == 200
