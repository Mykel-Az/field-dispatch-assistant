import datetime

from .conftest import client_for

FULL = {
    "name": "Cool Air Ltd",
    "lat": 6.5244,
    "lng": 3.3792,
    "work_start": "08:00:00",
    "work_end": "17:00:00",
}


def test_dispatcher_and_head_can_read(head_a, dispatcher_a):
    for user in (head_a, dispatcher_a):
        response = client_for(user).get("/api/organization/")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Org A"
        assert body["version"] == 1
        assert body["is_configured"] is False


def test_only_head_can_write(dispatcher_a):
    response = client_for(dispatcher_a).patch(
        "/api/organization/", {"version": 1, "name": "X"}, format="json"
    )
    assert response.status_code == 403


def test_patch_updates_bumps_version_and_marks_manual_geocode(head_a, org_a):
    response = client_for(head_a).patch(
        "/api/organization/", {"version": 1, **FULL}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Cool Air Ltd"
    assert body["version"] == 2
    assert body["geocode_status"] == "manual"
    assert body["is_configured"] is True
    org_a.refresh_from_db()
    assert org_a.work_start == datetime.time(8)


def test_stale_version_is_a_409(head_a):
    client = client_for(head_a)
    first = client.patch(
        "/api/organization/", {"version": 1, "name": "One"}, format="json"
    )
    assert first.status_code == 200
    stale = client.patch(
        "/api/organization/", {"version": 1, "name": "Two"}, format="json"
    )
    assert stale.status_code == 409
    assert client.get("/api/organization/").json()["name"] == "One"


def test_version_is_required_on_patch(head_a):
    response = client_for(head_a).patch(
        "/api/organization/", {"name": "X"}, format="json"
    )
    assert response.status_code == 400


def test_validation(head_a):
    client = client_for(head_a)
    bad_hours = {"version": 1, "work_start": "17:00", "work_end": "08:00"}
    bad_lat = {"version": 1, "lat": 123}
    assert (
        client.patch("/api/organization/", bad_hours, format="json").status_code == 400
    )
    assert client.patch("/api/organization/", bad_lat, format="json").status_code == 400


def test_each_head_changes_only_their_own_organization(head_a, head_b, org_a, org_b):
    client_for(head_b).patch(
        "/api/organization/", {"version": 1, "name": "B2"}, format="json"
    )
    org_a.refresh_from_db()
    org_b.refresh_from_db()
    assert (org_a.name, org_b.name) == ("Org A", "B2")


def test_id_and_geocode_status_cannot_be_written(head_a, org_a):
    response = client_for(head_a).patch(
        "/api/organization/",
        {"version": 1, "id": 999, "geocode_status": "ok"},
        format="json",
    )
    assert response.status_code == 200
    org_a.refresh_from_db()
    assert org_a.pk != 999 and org_a.geocode_status == "pending"
