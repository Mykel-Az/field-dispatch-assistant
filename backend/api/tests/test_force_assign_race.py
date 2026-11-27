import datetime
import threading

import pytest
from django.db import connection

from api.models import Job, JobStatus, JobStatusHistory, Skill
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import make_job, technician_of

UTC = datetime.UTC
NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago
DAY = datetime.date(2026, 11, 2)


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="needs real row locks (CI runs Postgres); SQLite cannot test this",
)
@pytest.mark.django_db(transaction=True)
def test_two_force_assigns_at_once_never_reuse_a_stop_or_bump_a_job_twice(
    org_a, dispatcher_a, technician_a
):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    hvac, _ = Skill.objects.get_or_create(name="HVAC")
    tech = technician_of(technician_a)
    tech.skills.add(hvac)
    low = make_job(
        org_a,
        status=JobStatus.ASSIGNED,
        technician=tech,
        sequence_position=1,
        estimated_arrival=NOW,
        estimated_duration_minutes=240,
        slot_start=NOW,
        slot_end=NOW + datetime.timedelta(hours=6),
        scheduled_date=DAY,
        priority="low",
        lat=30.30,
        lng=-97.70,
    )
    urgents = [
        make_job(
            org_a,
            is_urgent=True,
            slot_start=None,
            slot_end=None,
            scheduled_date=DAY,
            estimated_duration_minutes=30,
            lat=30.30,
            lng=-97.70,
        )
        for _ in range(2)
    ]
    Job.objects.filter(pk__in=[u.pk for u in urgents]).update(created_at=NOW)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def run(job):
        try:
            barrier.wait()
            results.append(
                scheduling.force_assign(
                    job=job,
                    technician=tech,
                    actor=dispatcher_a,
                    client_version=job.version,
                    clock=FixedClock(NOW),
                )
            )
        except Exception as error:  # noqa: BLE001 - report it from the main thread
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(u,)) for u in urgents]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    bumped = [pk for r in results for pk in r.bumped_job_ids]
    assert bumped.count(low.pk) <= 1  # the low job goes back to the queue once
    assert (
        JobStatusHistory.objects.filter(job=low, to_status=JobStatus.UNASSIGNED).count()
        == 1
    )
    assigned = Job.objects.filter(technician=tech, status=JobStatus.ASSIGNED)
    positions = sorted(assigned.values_list("sequence_position", flat=True))
    assert positions == list(range(1, len(positions) + 1))  # no number used twice
    for urgent in urgents:
        assert Job.objects.get(pk=urgent.pk).technician_id == tech.pk
