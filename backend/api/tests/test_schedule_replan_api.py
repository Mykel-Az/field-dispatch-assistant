"""POST /api/schedule/generate/ with `replan` (ADR-026)."""

import datetime

import pytest
from rest_framework.test import APIClient

URL = "/api/schedule/generate/"


@pytest.fixture
def client(dispatcher_a):
    c = APIClient()
    c.force_authenticate(dispatcher_a)
    return c


def test_replan_defaults_to_off_and_is_accepted_when_on(client, org_a):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    assert client.post(URL, {}, format="json").status_code == 200
    on = client.post(URL, {"replan": True}, format="json")
    assert on.status_code == 200
    assert on.data["assigned"] == [] and on.data["unassigned"] == []


def test_replan_must_be_a_boolean(client):
    response = client.post(URL, {"replan": "maybe"}, format="json")
    assert response.status_code == 400 and "replan" in response.data


def test_a_technician_cannot_replan(technician_a):
    c = APIClient()
    c.force_authenticate(technician_a)
    assert c.post(URL, {"replan": True}, format="json").status_code == 403
