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


def test_organization_phone_with_letters_is_rejected(head_a):
    response = client_for(head_a).patch(
        "/api/organization/", {"version": 1, "phone": "call us"}, format="json"
    )
    assert response.status_code == 400


# ---- time zone --------------------------------------------------------------
def test_new_organizations_default_to_central(org_a):
    assert org_a.timezone == "America/Chicago"


def test_head_can_change_the_timezone_and_bad_zones_are_refused(head_a):
    client = client_for(head_a)
    ok = client.patch(
        "/api/organization/",
        {"version": 1, "timezone": "America/Los_Angeles"},
        format="json",
    )
    assert ok.status_code == 200 and ok.json()["timezone"] == "America/Los_Angeles"
    bad = client.patch(
        "/api/organization/", {"version": 2, "timezone": "Africa/Lagos"}, format="json"
    )
    assert bad.status_code == 400 and "timezone" in bad.json()


def test_a_late_evening_slot_belongs_to_the_organizations_day(dispatcher_a):
    # 02:00 UTC on 3 Nov is 20:00 on 2 Nov in Chicago (CST, UTC-6).
    response = client_for(dispatcher_a).post(
        "/api/jobs/",
        {
            "title": "Late call",
            "customer_name": "Ada",
            "category": "hvac",
            "address": "1 Main St",
            "postal_code": "78701",
            "slot_start": "2026-11-03T02:00:00Z",
            "slot_end": "2026-11-03T03:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["scheduled_date"] == "2026-11-02"


def test_changing_the_timezone_moves_existing_jobs_to_the_right_day(head_a, org_a):
    from api.tests.conftest import make_job

    # 08:00 UTC on 3 Nov: 02:00 on 3 Nov in Chicago (UTC-6), 22:00 on 2 Nov in Honolulu (UTC-10).
    job = make_job(
        org_a,
        slot_start=datetime.datetime(2026, 11, 3, 8, tzinfo=datetime.UTC),
        slot_end=datetime.datetime(2026, 11, 3, 9, tzinfo=datetime.UTC),
        scheduled_date=datetime.date(2026, 11, 3),
    )
    client = client_for(head_a)
    client.patch(
        "/api/organization/",
        {"version": 1, "timezone": "Pacific/Honolulu"},
        format="json",
    )
    job.refresh_from_db()
    assert job.scheduled_date == datetime.date(2026, 11, 2)
    client.patch(
        "/api/organization/",
        {"version": 2, "timezone": "America/Chicago"},
        format="json",
    )
    job.refresh_from_db()
    assert job.scheduled_date == datetime.date(2026, 11, 3)


def test_urgent_jobs_keep_their_day_when_the_zone_changes(head_a, org_a):
    from api.tests.conftest import make_job

    job = make_job(
        org_a,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        scheduled_date=datetime.date(2026, 11, 3),
    )
    client_for(head_a).patch(
        "/api/organization/",
        {"version": 1, "timezone": "Pacific/Honolulu"},
        format="json",
    )
    job.refresh_from_db()
    assert job.scheduled_date == datetime.date(2026, 11, 3)
