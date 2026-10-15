import threading

import pytest
from django.db import connection

from api.models import CustomUser
from api.services.accounts import LastHeadError, deactivate_user

from .conftest import Role, make_user


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="needs real row locks (CI runs Postgres); SQLite cannot test this",
)
@pytest.mark.django_db(transaction=True)
def test_two_heads_deactivating_each_other_leave_one_active(org_a):
    first = make_user(org_a, Role.HEAD_DISPATCHER, "h1@example.com")
    second = make_user(org_a, Role.HEAD_DISPATCHER, "h2@example.com")
    barrier = threading.Barrier(2)
    results = []

    def attempt(actor, target):
        try:
            barrier.wait()
            deactivate_user(actor=actor, target=target)
            results.append("ok")
        except LastHeadError:
            results.append("last_head")
        finally:
            connection.close()

    threads = [
        threading.Thread(target=attempt, args=(first, second)),
        threading.Thread(target=attempt, args=(second, first)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["last_head", "ok"]
    active = CustomUser.objects.filter(
        organization=org_a, role=Role.HEAD_DISPATCHER, is_active=True
    )
    assert active.count() == 1
