import pytest

from api.models import Job, JobStatusHistory
from api.services import jobs as svc

from .conftest import make_job, technician_of


@pytest.fixture
def tech(technician_a):
    return technician_of(technician_a)


def history(job):
    return list(JobStatusHistory.objects.filter(job=job).order_by("id"))


def test_assign_writes_one_history_row_and_bumps_version(org_a, dispatcher_a, tech):
    job = make_job(org_a)
    job = svc.transition(job, "assigned", dispatcher_a, technician=tech)
    assert (job.status, job.technician_id, job.version) == ("assigned", tech.pk, 2)
    [row] = history(job)
    assert (row.from_status, row.to_status) == ("unassigned", "assigned")
    assert row.changed_by == dispatcher_a and row.technician_id == tech.pk


def test_assign_requires_a_technician(org_a, dispatcher_a):
    with pytest.raises(ValueError):
        svc.transition(make_job(org_a), "assigned", dispatcher_a)


def test_assign_refuses_a_job_without_a_location(org_a, dispatcher_a, tech):  # inv 16
    job = make_job(org_a, geocode_status="failed")
    with pytest.raises(svc.LocationRequired):
        svc.transition(job, "assigned", dispatcher_a, technician=tech)
    assert history(job) == []


def test_rejected_transition_changes_and_writes_nothing(org_a, dispatcher_a):
    job = make_job(org_a)
    with pytest.raises(svc.IllegalJobTransition):
        svc.transition(job, "completed", dispatcher_a)
    job.refresh_from_db()
    assert (job.status, job.version) == ("unassigned", 1)
    assert history(job) == []


def test_terminal_job_cannot_move(org_a, dispatcher_a):
    job = svc.transition(make_job(org_a), "canceled", dispatcher_a, "customer left")
    with pytest.raises(svc.IllegalJobTransition):
        svc.transition(job, "unassigned", dispatcher_a)
    assert len(history(job)) == 1


@pytest.mark.parametrize("blank", ["", "   "])
def test_cancel_needs_a_reason(org_a, dispatcher_a, blank):
    job = make_job(org_a)
    with pytest.raises(svc.ReasonRequired):
        svc.transition(job, "canceled", dispatcher_a, blank)
    assert history(job) == []


def test_canceling_an_assigned_job_frees_the_technician_and_the_stop(
    org_a, dispatcher_a, tech
):
    job = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    job = svc.cancel_job(job=job, actor=dispatcher_a, reason="no longer needed")
    assert (job.status, job.technician_id, job.sequence_position) == (
        "canceled",
        None,
        None,
    )
    assert history(job)[-1].technician_id == tech.pk  # the audit trail remembers


def test_cancel_is_idempotent(org_a, dispatcher_a):
    job = make_job(org_a)
    first = svc.cancel_job(job=job, actor=dispatcher_a, reason="dup")
    second = svc.cancel_job(job=job, actor=dispatcher_a, reason="dup")
    assert second.version == first.version
    assert len(history(job)) == 1


def test_cannot_cancel_an_ongoing_job(org_a, dispatcher_a, tech):
    job = make_job(org_a, status="ongoing", technician=tech)
    with pytest.raises(svc.IllegalJobTransition):
        svc.cancel_job(job=job, actor=dispatcher_a, reason="x")


def test_incomplete_returns_to_the_queue_with_a_reason(
    org_a, dispatcher_a, tech
):  # inv 9
    job = make_job(org_a, status="ongoing", technician=tech, sequence_position=1)
    job = svc.transition(job, "incomplete", dispatcher_a, "part missing")
    assert job.technician_id == tech.pk and job.completed_at is not None
    job = svc.transition(job, "unassigned", dispatcher_a)
    assert (job.technician_id, job.sequence_position) == (None, None)
    assert [r.to_status for r in history(job)] == ["incomplete", "unassigned"]
    assert history(job)[0].reason == "part missing"


def test_release_returns_assigned_jobs_and_skips_ongoing(org_a, dispatcher_a, tech):
    one = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    two = make_job(org_a, status="assigned", technician=tech, sequence_position=2)
    busy = make_job(org_a, status="ongoing", technician=tech)
    assert svc.release_assigned_jobs(tech, dispatcher_a) == 2
    for job in (one, two):
        job.refresh_from_db()
        assert (job.status, job.technician_id) == ("unassigned", None)
        assert history(job)[-1].reason == "technician deactivated"
    busy.refresh_from_db()
    assert busy.status == "ongoing" and history(busy) == []


def test_only_the_service_writes_history_rows_per_change(org_a, dispatcher_a, tech):
    job = make_job(org_a)
    svc.transition(job, "assigned", dispatcher_a, technician=tech)
    svc.transition(job, "unassigned", dispatcher_a)
    assert Job.objects.get(pk=job.pk).version == 3
    assert len(history(job)) == 2
