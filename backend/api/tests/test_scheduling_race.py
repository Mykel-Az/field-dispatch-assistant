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
def test_two_runs_at_once_never_double_assign_or_reuse_a_stop_number(
    org_a, dispatcher_a, technician_a
):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.max_jobs_per_tech_per_day = 10
    org_a.save()
    # transaction=True tests empty the tables afterwards, seeded skills included
    hvac, _ = Skill.objects.get_or_create(name="HVAC")
    technician_of(technician_a).skills.add(hvac)
    jobs = [
        make_job(
            org_a,
            slot_start=NOW + datetime.timedelta(hours=1 + i),
            slot_end=NOW + datetime.timedelta(hours=2 + i),
            scheduled_date=DAY,
        )
        for i in range(4)
    ]
    barrier = threading.Barrier(2)
    results, errors = [], []

    def run():
        try:
            barrier.wait()
            results.append(
                scheduling.generate_schedule(
                    organization=org_a,
                    actor=dispatcher_a,
                    plan_date=DAY,
                    clock=FixedClock(NOW),
                )
            )
        except Exception as error:  # noqa: BLE001 - report it from the main thread
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    planned = [p.job_id for r in results for p in r.assigned]
    assert sorted(planned) == sorted(
        j.pk for j in jobs
    )  # each job planned once overall
    for job in jobs:
        assert (
            JobStatusHistory.objects.filter(
                job=job, to_status=JobStatus.ASSIGNED
            ).count()
            == 1
        )
    positions = list(
        Job.objects.filter(status=JobStatus.ASSIGNED).values_list(
            "sequence_position", flat=True
        )
    )
    assert sorted(positions) == [1, 2, 3, 4]
