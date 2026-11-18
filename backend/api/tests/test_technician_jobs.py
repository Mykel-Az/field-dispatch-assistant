"""S2-7: the technician's own day and the three actions: arrive, complete, incomplete."""

import datetime

import pytest

from api.models import Job, JobStatus, JobStatusHistory
from api.services import jobs as job_service

from .conftest import Role, client_for, make_job, make_user, technician_of

DAY = datetime.date(2026, 11, 2)
LIST = "/api/technician/me/jobs/"


def url(job, action):
    return f"/api/technician/me/jobs/{job.pk}/{action}/"


@pytest.fixture
def me(org_a, technician_a):
    return technician_of(technician_a)


@pytest.fixture
def colleague(org_a):
    user = make_user(org_a, Role.TECHNICIAN, "tech-2@example.com")
    return technician_of(user)


@pytest.fixture
def client(technician_a):
    return client_for(technician_a)


def assigned(org, technician, dispatcher, position=1, **fields):
    job = make_job(org, **fields)
    job_service.transition(job, "assigned", dispatcher, technician=technician)
    Job.objects.filter(pk=job.pk).update(sequence_position=position)
    return Job.objects.get(pk=job.pk)


# ---- the list -------------------------------------------------------------------
def test_the_list_holds_only_my_jobs_for_the_day_in_visit_order(
    client, org_a, me, colleague, dispatcher_a, org_b
):
    second = assigned(org_a, me, dispatcher_a, position=2, title="Second")
    first = assigned(org_a, me, dispatcher_a, position=1, title="First")
    done = assigned(org_a, me, dispatcher_a, position=3, title="Done")
    job_service.transition(done, "ongoing", dispatcher_a)
    job_service.transition(done, "completed", dispatcher_a)
    assigned(org_a, colleague, dispatcher_a, title="Not mine")
    make_job(org_a, title="In the queue")
    other_day = assigned(
        org_a, me, dispatcher_a, position=4, title="Tomorrow",
        scheduled_date=DAY + datetime.timedelta(days=1),
    )  # fmt: skip

    response = client.get(LIST, {"date": DAY.isoformat()})

    assert response.status_code == 200
    assert [j["title"] for j in response.data] == ["First", "Second", "Done"]
    assert other_day.title not in [j["title"] for j in response.data]
    assert {j["id"] for j in response.data} == {first.pk, second.pk, done.pk}


def test_a_job_returned_to_the_queue_leaves_my_list(client, org_a, me, dispatcher_a):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    client.post(url(job, "incomplete"), {"reason": "No access"}, format="json")
    assert client.get(LIST, {"date": DAY.isoformat()}).data == []


def test_the_list_shows_the_field_details_and_none_of_the_office_internals(
    client, org_a, me, dispatcher_a
):
    assigned(org_a, me, dispatcher_a, customer_phone="512-555-0100")
    (row,) = client.get(LIST, {"date": DAY.isoformat()}).data
    assert row["customer_phone"] == "512-555-0100" and row["address"] == "1 Main St"
    assert not {"history", "version", "plan_explanation", "technician"} & set(row)


def test_a_bad_date_is_a_400(client):
    assert client.get(LIST, {"date": "tomorrow"}).status_code == 400


# ---- arrive -----------------------------------------------------------------------
def test_arrive_starts_the_job_and_writes_one_history_row(
    client, org_a, me, dispatcher_a, technician_a
):
    job = assigned(org_a, me, dispatcher_a)
    response = client.post(url(job, "arrive"))
    assert response.status_code == 200
    assert response.data["status"] == "ongoing" and response.data["arrived_at"]
    row = JobStatusHistory.objects.filter(job=job, to_status="ongoing").get()
    assert row.changed_by == technician_a and row.from_status == "assigned"


def test_arrive_twice_is_a_200_and_writes_no_second_row(
    client, org_a, me, dispatcher_a
):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    again = client.post(url(job, "arrive"))
    assert again.status_code == 200 and again.data["status"] == "ongoing"
    assert JobStatusHistory.objects.filter(job=job, to_status="ongoing").count() == 1


def test_a_second_ongoing_job_is_refused_and_the_first_stays_ongoing(
    client, org_a, me, dispatcher_a
):
    first = assigned(org_a, me, dispatcher_a, position=1)
    second = assigned(org_a, me, dispatcher_a, position=2)
    client.post(url(first, "arrive"))
    response = client.post(url(second, "arrive"))
    assert response.status_code == 409
    assert response.data["detail"].code == "another_job_ongoing"
    assert Job.objects.get(pk=first.pk).status == JobStatus.ONGOING
    assert Job.objects.get(pk=second.pk).status == JobStatus.ASSIGNED


def test_the_next_job_can_start_once_the_first_is_done(client, org_a, me, dispatcher_a):
    first = assigned(org_a, me, dispatcher_a, position=1)
    second = assigned(org_a, me, dispatcher_a, position=2)
    client.post(url(first, "arrive"))
    client.post(url(first, "complete"))
    assert client.post(url(second, "arrive")).status_code == 200


@pytest.mark.parametrize("state", ["completed", "canceled"])
def test_arrive_on_a_job_in_the_wrong_state_is_409(
    client, org_a, me, dispatcher_a, state
):
    job = assigned(org_a, me, dispatcher_a)
    if state == "completed":
        job_service.transition(job, "ongoing", dispatcher_a)
        job_service.transition(job, "completed", dispatcher_a)
    else:
        job_service.cancel_job(job=job, actor=dispatcher_a, reason="Customer called")
        Job.objects.filter(pk=job.pk).update(technician=me)  # still theirs on paper
    response = client.post(url(job, "arrive"))
    assert (
        response.status_code == 409
        and response.data["detail"].code == "illegal_transition"
    )


# ---- complete -----------------------------------------------------------------------
def test_complete_finishes_an_ongoing_job_and_is_safe_to_repeat(
    client, org_a, me, dispatcher_a
):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    response = client.post(url(job, "complete"))
    assert response.status_code == 200 and response.data["status"] == "completed"
    assert response.data["completed_at"]
    assert client.post(url(job, "complete")).status_code == 200
    assert JobStatusHistory.objects.filter(job=job, to_status="completed").count() == 1


def test_complete_before_arriving_is_409(client, org_a, me, dispatcher_a):
    job = assigned(org_a, me, dispatcher_a)
    response = client.post(url(job, "complete"))
    assert (
        response.status_code == 409
        and response.data["detail"].code == "illegal_transition"
    )


# ---- incomplete ------------------------------------------------------------------------
def test_incomplete_needs_a_reason(client, org_a, me, dispatcher_a):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    for body in ({}, {"reason": ""}, {"reason": "   "}):
        assert (
            client.post(url(job, "incomplete"), body, format="json").status_code == 400
        )
    assert Job.objects.get(pk=job.pk).status == JobStatus.ONGOING


def test_incomplete_sends_the_job_back_to_the_queue_with_the_story(
    client, org_a, me, dispatcher_a, technician_a
):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    response = client.post(
        url(job, "incomplete"), {"reason": "Part not on the truck"}, format="json"
    )
    assert response.status_code == 200 and response.data["status"] == "unassigned"
    saved = Job.objects.get(pk=job.pk)
    assert saved.technician is None and saved.attempt_count == 1
    rows = list(
        JobStatusHistory.objects.filter(
            job=job, from_status__in=["ongoing", "incomplete"]
        )
    )
    assert [(r.to_status, r.changed_by) for r in rows] == [
        ("incomplete", technician_a),
        ("unassigned", technician_a),
    ]
    assert rows[0].reason == "Part not on the truck"
    assert rows[0].technician_id == me.pk


def test_incomplete_twice_is_a_200_and_writes_nothing_more(
    client, org_a, me, dispatcher_a
):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    client.post(url(job, "incomplete"), {"reason": "No access"}, format="json")
    count = JobStatusHistory.objects.filter(job=job).count()
    again = client.post(url(job, "incomplete"), {"reason": "No access"}, format="json")
    assert again.status_code == 200 and again.data["status"] == "unassigned"
    assert JobStatusHistory.objects.filter(job=job).count() == count


def test_incomplete_before_arriving_is_409(client, org_a, me, dispatcher_a):
    job = assigned(org_a, me, dispatcher_a)
    response = client.post(url(job, "incomplete"), {"reason": "x"}, format="json")
    assert (
        response.status_code == 409
        and response.data["detail"].code == "illegal_transition"
    )


def test_repeating_incomplete_after_the_job_moved_on_is_404(
    client, org_a, me, colleague, dispatcher_a
):
    job = assigned(org_a, me, dispatcher_a)
    client.post(url(job, "arrive"))
    client.post(url(job, "incomplete"), {"reason": "No access"}, format="json")
    job_service.transition(job, "assigned", dispatcher_a, technician=colleague)
    response = client.post(
        url(job, "incomplete"), {"reason": "No access"}, format="json"
    )
    assert response.status_code == 404


# ---- whose job it is --------------------------------------------------------------------
@pytest.mark.parametrize("action", ["arrive", "complete", "incomplete"])
def test_someone_elses_job_is_404_and_untouched(
    client, org_a, colleague, dispatcher_a, action
):
    theirs = assigned(org_a, colleague, dispatcher_a)
    response = client.post(url(theirs, action), {"reason": "x"}, format="json")
    assert response.status_code == 404
    assert Job.objects.get(pk=theirs.pk).status == JobStatus.ASSIGNED


def test_an_unassigned_job_is_404_for_a_technician(client, org_a):
    job = make_job(org_a)
    assert client.post(url(job, "arrive")).status_code == 404


def test_a_dispatcher_cannot_use_the_technician_endpoints(org_a, me, dispatcher_a):
    job = assigned(org_a, me, dispatcher_a)
    assert client_for(dispatcher_a).post(url(job, "arrive")).status_code == 403
    assert client_for(dispatcher_a).get(LIST).status_code == 403
