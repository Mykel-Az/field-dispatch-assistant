import threading

import pytest
from django.db import connection

from api.models import Job

from .conftest import client_for, make_job


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="needs real row locks (CI runs Postgres); SQLite cannot test this",
)
@pytest.mark.django_db(transaction=True)
def test_two_edits_with_the_same_version_one_wins_one_gets_409(dispatcher_a, org_a):
    job = make_job(org_a)
    barrier = threading.Barrier(2)
    codes = []

    def attempt(title):
        try:
            client = client_for(dispatcher_a)
            barrier.wait()
            response = client.patch(
                f"/api/jobs/{job.pk}/", {"version": 1, "title": title}, format="json"
            )
            codes.append(response.status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(t,)) for t in ("one", "two")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(codes) == [200, 409]
    assert Job.objects.get(pk=job.pk).version == 2
