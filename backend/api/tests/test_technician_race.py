"""Two requests for the same technician at the same instant (needs real row locks)."""

import threading

import pytest
from django.db import connection

from api.models import Job, JobStatus, JobStatusHistory
from api.services import jobs as job_service

from .conftest import make_job, technician_of

pytestmark = [
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="needs real row locks (CI runs Postgres); SQLite cannot test this",
    ),
    pytest.mark.django_db(transaction=True),
]


def assigned(org, technician, dispatcher, position):
    job = make_job(org)
    job_service.transition(job, "assigned", dispatcher, technician=technician)
    Job.objects.filter(pk=job.pk).update(sequence_position=position)
    return Job.objects.get(pk=job.pk)


def run_together(calls):
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def attempt(i, call):
        try:
            barrier.wait()
            results[i] = call().status
        except job_service.AnotherJobOngoing:
            results[i] = "another_job_ongoing"
        finally:
            connection.close()

    threads = [
        threading.Thread(target=attempt, args=(i, c)) for i, c in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_arrivals_for_the_same_technician_start_only_one_job(
    org_a, dispatcher_a, technician_a
):
    me = technician_of(technician_a)
    first = assigned(org_a, me, dispatcher_a, 1)
    second = assigned(org_a, me, dispatcher_a, 2)

    results = run_together(
        [
            lambda: job_service.arrive_job(
                job=first, technician=me, actor=technician_a
            ),
            lambda: job_service.arrive_job(
                job=second, technician=me, actor=technician_a
            ),
        ]
    )

    assert sorted(results) == ["another_job_ongoing", "ongoing"]
    assert Job.objects.filter(technician=me, status=JobStatus.ONGOING).count() == 1


def test_the_same_arrival_sent_twice_at_once_is_one_change(
    org_a, dispatcher_a, technician_a
):
    me = technician_of(technician_a)
    job = assigned(org_a, me, dispatcher_a, 1)

    results = run_together(
        [lambda: job_service.arrive_job(job=job, technician=me, actor=technician_a)] * 2
    )

    assert results == ["ongoing", "ongoing"]
    assert JobStatusHistory.objects.filter(job=job, to_status="ongoing").count() == 1


def test_the_same_incomplete_sent_twice_at_once_is_one_change(
    org_a, dispatcher_a, technician_a
):
    me = technician_of(technician_a)
    job = assigned(org_a, me, dispatcher_a, 1)
    job_service.arrive_job(job=job, technician=me, actor=technician_a)

    results = run_together(
        [
            lambda: job_service.incomplete_job(
                job=job, technician=me, actor=technician_a, reason="No access"
            )
        ]
        * 2
    )

    assert results == ["unassigned", "unassigned"]
    assert JobStatusHistory.objects.filter(job=job, to_status="incomplete").count() == 1
    assert Job.objects.get(pk=job.pk).attempt_count == 1
