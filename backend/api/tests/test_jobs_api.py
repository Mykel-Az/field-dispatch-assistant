import datetime

import pytest
from rest_framework.test import APIClient

from api.models import CandidateSkillRule, Job, JobStatusHistory, Skill

from .conftest import client_for, make_job, technician_of

SLOT = {"slot_start": "2026-11-02T09:00:00Z", "slot_end": "2026-11-02T11:00:00Z"}


def body(**overrides):
    data = {
        "title": "Fix AC",
        "customer_name": "Ada Customer",
        "category": "hvac",
        "address": "1 Main St",
        "postal_code": "78701",
        **SLOT,
    }
    data.update(overrides)
    return data


def skill(name):
    return Skill.objects.get(name=name)


# ---- seed -------------------------------------------------------------------
def test_category_rules_are_seeded(db):
    pairs = set(CandidateSkillRule.objects.values_list("category", "skill__name"))
    assert pairs == {
        ("hvac", "HVAC"),
        ("electrical", "Electrical"),
        ("appliance", "Appliance Repair"),
    }


# ---- create -----------------------------------------------------------------
def test_create_uses_category_default_skills_and_writes_history(dispatcher_a):
    response = client_for(dispatcher_a).post("/api/jobs/", body(), format="json")
    assert response.status_code == 201, response.content
    data = response.json()
    assert [s["name"] for s in data["acceptable_skills"]] == ["HVAC"]
    assert data["status"] == "unassigned" and data["version"] == 1
    assert data["scheduled_date"] == "2026-11-02"
    assert data["geocode_status"] == "ok" and data["location_label"]
    assert (
        data["lat"] is not None and data["lng"] is not None
    )  # the location panel draws it
    [row] = data["history"]
    assert (row["from_status"], row["to_status"]) == ("", "unassigned")
    assert row["changed_by"]["id"] == dispatcher_a.pk


def test_create_goes_into_the_requesters_organization(dispatcher_a, org_a, org_b):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(organization=org_b.pk), format="json"
    )
    assert response.status_code == 201
    assert Job.objects.get(pk=response.json()["id"]).organization == org_a


def test_dispatcher_may_override_skills(dispatcher_a):
    ids = [skill("Electrical").pk, skill("HVAC").pk]
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(skill_ids=ids), format="json"
    )
    names = {s["name"] for s in response.json()["acceptable_skills"]}
    assert names == {"Electrical", "HVAC"}


def test_an_empty_skill_list_falls_back_to_the_category_defaults(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(skill_ids=[]), format="json"
    )
    assert [s["name"] for s in response.json()["acceptable_skills"]] == ["HVAC"]


def test_no_skills_at_all_is_a_400(dispatcher_a):
    CandidateSkillRule.objects.filter(category="hvac").delete()
    response = client_for(dispatcher_a).post("/api/jobs/", body(), format="json")
    assert response.status_code == 400
    assert response.json()["skill_ids"] == ["Select at least one skill."]


@pytest.mark.parametrize("zip_code", ["1234", "abcde", "123456", "12345-67", ""])
def test_bad_zip_is_a_400(dispatcher_a, zip_code):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(postal_code=zip_code), format="json"
    )
    assert response.status_code == 400 and "postal_code" in response.json()


@pytest.mark.parametrize("zip_code", ["78701", "78701-1234"])
def test_good_zip_formats(dispatcher_a, zip_code):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(postal_code=zip_code), format="json"
    )
    assert response.status_code == 201


def test_non_urgent_job_needs_a_slot(dispatcher_a):
    data = body()
    del data["slot_start"], data["slot_end"]
    response = client_for(dispatcher_a).post("/api/jobs/", data, format="json")
    assert response.status_code == 400 and "slot_start" in response.json()


def test_slot_end_must_be_after_start(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(slot_end=SLOT["slot_start"]), format="json"
    )
    assert response.status_code == 400 and "slot_end" in response.json()


def test_only_one_slot_time_is_a_400(dispatcher_a):
    data = body()
    del data["slot_end"]
    response = client_for(dispatcher_a).post("/api/jobs/", data, format="json")
    assert response.status_code == 400 and "slot_end" in response.json()


def test_urgent_job_needs_no_slot_and_is_scheduled_today(dispatcher_a):
    data = body(is_urgent=True)
    del data["slot_start"], data["slot_end"]
    response = client_for(dispatcher_a).post("/api/jobs/", data, format="json")
    assert response.status_code == 201
    out = response.json()
    assert out["slot_start"] is None and out["scheduled_date"] is not None


def test_failed_geocoding_does_not_fail_the_request(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(address="boom street"), format="json"
    )
    assert response.status_code == 201
    assert response.json()["geocode_status"] == "failed"


def test_unfindable_address_is_flagged_not_rejected(dispatcher_a):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(address="unfindable lane"), format="json"
    )
    assert response.status_code == 201
    assert response.json()["geocode_status"] == "failed"


@pytest.mark.parametrize("field", ["status", "technician", "version", "lat", "lng"])
def test_protected_fields_are_ignored_on_create(dispatcher_a, field):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", body(**{field: 99}), format="json"
    )
    assert response.status_code == 201
    job = Job.objects.get(pk=response.json()["id"])
    assert (job.status, job.technician_id, job.version) == ("unassigned", None, 1)
    assert job.lat != 99


# ---- read -------------------------------------------------------------------
def test_list_shape_and_isolation(dispatcher_a, org_a, org_b):
    mine = make_job(org_a)
    make_job(org_b)
    response = client_for(dispatcher_a).get("/api/jobs/")
    assert response.status_code == 200
    [row] = response.json()["results"]
    assert row["id"] == mine.pk
    assert set(row) == {
        "id", "title", "customer_name", "address", "postal_code", "category",
        "is_urgent", "status", "technician", "scheduled_date", "slot_start",
        "slot_end", "geocode_status", "location_label",
    }  # fmt: skip


def test_list_shows_the_technician_name(dispatcher_a, org_a, technician_a):
    tech = technician_of(technician_a)
    make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    [row] = client_for(dispatcher_a).get("/api/jobs/").json()["results"]
    assert row["technician"] == {"id": tech.pk, "full_name": technician_a.full_name}


def test_list_does_not_run_a_query_per_job(
    dispatcher_a, org_a, technician_a, django_assert_max_num_queries
):
    tech = technician_of(technician_a)
    for i in range(6):
        make_job(org_a, status="assigned", technician=tech, sequence_position=i + 1)
    client = client_for(dispatcher_a)
    with django_assert_max_num_queries(6):  # session, user, org, count, jobs
        assert client.get("/api/jobs/").status_code == 200


def test_detail_does_not_run_a_query_per_history_row(
    dispatcher_a, org_a, technician_a, django_assert_max_num_queries
):
    job = make_job(org_a)
    for _ in range(5):
        JobStatusHistory.objects.create(
            organization=org_a, job=job, to_status="unassigned", changed_by=dispatcher_a
        )
    client = client_for(dispatcher_a)
    with django_assert_max_num_queries(7):
        assert client.get(f"/api/jobs/{job.pk}/").status_code == 200


def test_filters(dispatcher_a, org_a, technician_a):
    tech = technician_of(technician_a)
    day2 = datetime.datetime(2026, 11, 3, 9, tzinfo=datetime.UTC)
    a = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    b = make_job(
        org_a, slot_start=day2, slot_end=day2 + datetime.timedelta(hours=1),
        scheduled_date=day2.date(),
    )  # fmt: skip
    client = client_for(dispatcher_a)

    def ids(query):
        rows = client.get(f"/api/jobs/?{query}").json()["results"]
        return {row["id"] for row in rows}

    assert ids("status=assigned") == {a.pk}
    assert ids("status=unassigned") == {b.pk}
    assert ids("scheduled_date=2026-11-03") == {b.pk}
    assert ids(f"technician={tech.pk}") == {a.pk}
    assert ids("status=assigned&scheduled_date=2026-11-03") == set()


@pytest.mark.parametrize(
    "query", ["status=bogus", "scheduled_date=tomorrow", "technician=x"]
)
def test_bad_filter_values_are_a_400(dispatcher_a, query):
    assert client_for(dispatcher_a).get(f"/api/jobs/?{query}").status_code == 400


def test_detail_has_history_and_skills(dispatcher_a, org_a):
    job = make_job(org_a, customer_phone="555-123-4567")
    JobStatusHistory.objects.create(
        organization=org_a, job=job, to_status="unassigned", changed_by=dispatcher_a
    )
    data = client_for(dispatcher_a).get(f"/api/jobs/{job.pk}/").json()
    assert data["customer_phone"] == "555-123-4567" and data["version"] == 1
    assert [s["name"] for s in data["acceptable_skills"]] == ["HVAC"]
    assert len(data["history"]) == 1


def test_other_organizations_job_is_404(head_b, org_a):
    job = make_job(org_a)
    assert client_for(head_b).get(f"/api/jobs/{job.pk}/").status_code == 404


# ---- no DELETE, no PUT ------------------------------------------------------
def test_delete_and_put_are_not_allowed(dispatcher_a, org_a):
    job = make_job(org_a)
    client = client_for(dispatcher_a)
    assert client.delete(f"/api/jobs/{job.pk}/").status_code == 405
    assert client.put(f"/api/jobs/{job.pk}/", body(), format="json").status_code == 405


# ---- PATCH + optimistic lock ------------------------------------------------
def patch(user, job, data):
    return client_for(user).patch(f"/api/jobs/{job.pk}/", data, format="json")


def test_patch_edits_and_bumps_version(dispatcher_a, org_a):
    job = make_job(org_a)
    response = patch(dispatcher_a, job, {"version": 1, "title": "New title"})
    assert response.status_code == 200, response.content
    assert (response.json()["title"], response.json()["version"]) == ("New title", 2)


def test_patch_without_version_is_a_400(dispatcher_a, org_a):
    response = patch(dispatcher_a, make_job(org_a), {"title": "x"})
    assert response.status_code == 400 and "version" in response.json()


def test_stale_version_is_a_409(dispatcher_a, org_a):
    job = make_job(org_a)
    assert patch(dispatcher_a, job, {"version": 1, "title": "first"}).status_code == 200
    response = patch(dispatcher_a, job, {"version": 1, "title": "second"})
    assert response.status_code == 409
    assert response.json()["detail"] and response.data["detail"].code == "stale_version"
    job.refresh_from_db()
    assert job.title == "first"


@pytest.mark.parametrize(
    "field", ["status", "technician", "organization", "lat", "history", "id"]
)
def test_patch_cannot_touch_protected_fields(dispatcher_a, org_a, field):
    job = make_job(org_a)
    response = patch(dispatcher_a, job, {"version": 1, field: "assigned"})
    assert response.status_code == 400 and field in response.json()
    job.refresh_from_db()
    assert (job.status, job.version) == ("unassigned", 1)


def test_changing_the_address_geocodes_again(dispatcher_a, org_a):
    job = make_job(org_a, lat=1.0, lng=1.0)
    response = patch(dispatcher_a, job, {"version": 1, "address": "9 Oak Ave"})
    assert response.status_code == 200
    job.refresh_from_db()
    assert job.address == "9 Oak Ave" and job.lat != 1.0


def test_a_failed_regeocode_flags_the_job_but_succeeds(dispatcher_a, org_a):
    job = make_job(org_a)
    response = patch(dispatcher_a, job, {"version": 1, "address": "boom road"})
    assert response.status_code == 200
    assert response.json()["geocode_status"] == "failed"


def test_unchanged_address_does_not_geocode_again(dispatcher_a, org_a):
    job = make_job(org_a, lat=1.0, lng=1.0)
    patch(dispatcher_a, job, {"version": 1, "address": job.address, "title": "t"})
    job.refresh_from_db()
    assert job.lat == 1.0


def test_changing_the_slot_updates_the_scheduled_date(dispatcher_a, org_a):
    job = make_job(org_a)
    response = patch(
        dispatcher_a,
        job,
        {
            "version": 1,
            "slot_start": "2026-11-05T09:00:00Z",
            "slot_end": "2026-11-05T10:00:00Z",
        },
    )
    assert response.status_code == 200
    assert response.json()["scheduled_date"] == "2026-11-05"


def test_slot_order_is_checked_against_the_stored_slot(dispatcher_a, org_a):
    job = make_job(org_a)  # stored slot ends 11:00
    response = patch(
        dispatcher_a, job, {"version": 1, "slot_start": "2026-11-02T12:00:00Z"}
    )
    assert response.status_code == 400


def test_plan_fields_are_locked_once_assigned(dispatcher_a, org_a, technician_a):
    tech = technician_of(technician_a)
    job = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    response = patch(dispatcher_a, job, {"version": 1, "address": "elsewhere"})
    assert response.status_code == 409
    assert response.data["detail"].code == "job_not_editable"
    job.refresh_from_db()
    assert (job.address, job.version) == ("1 Main St", 1)


def test_plan_field_sent_unchanged_is_not_a_conflict(dispatcher_a, org_a, technician_a):
    tech = technician_of(technician_a)
    job = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    response = patch(
        dispatcher_a, job, {"version": 1, "address": job.address, "title": "Renamed"}
    )
    assert response.status_code == 200 and response.json()["title"] == "Renamed"


def test_skills_are_locked_once_assigned(dispatcher_a, org_a, technician_a):
    tech = technician_of(technician_a)
    job = make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    response = patch(
        dispatcher_a, job, {"version": 1, "skill_ids": [skill("Electrical").pk]}
    )
    assert response.status_code == 409


def test_patch_cannot_clear_the_skills(dispatcher_a, org_a):
    response = patch(dispatcher_a, make_job(org_a), {"version": 1, "skill_ids": []})
    assert response.status_code == 400
    assert response.json()["skill_ids"] == ["Select at least one skill."]


# ---- cancel -----------------------------------------------------------------
def cancel(user, job, reason="customer called"):
    return client_for(user).post(
        f"/api/jobs/{job.pk}/cancel/", {"reason": reason}, format="json"
    )


def test_cancel_unassigned_job(dispatcher_a, org_a):
    job = make_job(org_a)
    response = cancel(dispatcher_a, job)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "canceled" and data["version"] == 2
    assert [h["to_status"] for h in data["history"]] == ["canceled"]
    assert data["history"][0]["reason"] == "customer called"


def test_cancel_assigned_job_releases_the_technician(dispatcher_a, org_a, technician_a):
    job = make_job(
        org_a,
        status="assigned",
        technician=technician_of(technician_a),
        sequence_position=1,
    )
    data = cancel(dispatcher_a, job).json()
    assert data["status"] == "canceled" and data["technician"] is None


def test_cancel_twice_is_200_with_one_history_row(dispatcher_a, org_a):
    job = make_job(org_a)
    cancel(dispatcher_a, job)
    again = cancel(dispatcher_a, job)
    assert again.status_code == 200
    assert JobStatusHistory.objects.filter(job=job).count() == 1


def test_cancel_needs_a_reason(dispatcher_a, org_a):
    job = make_job(org_a)
    response = client_for(dispatcher_a).post(
        f"/api/jobs/{job.pk}/cancel/", {}, format="json"
    )
    assert response.status_code == 400 and "reason" in response.json()
    job.refresh_from_db()
    assert job.status == "unassigned"


def test_cancel_an_ongoing_job_is_a_409(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, status="ongoing", technician=technician_of(technician_a))
    response = cancel(dispatcher_a, job)
    assert response.status_code == 409
    assert response.data["detail"].code == "illegal_transition"


def test_cancel_a_completed_job_is_a_409(dispatcher_a, org_a):
    job = make_job(org_a, status="completed")
    assert cancel(dispatcher_a, job).status_code == 409


# ---- who may call -----------------------------------------------------------
@pytest.mark.parametrize(("who", "expected"), [("technician", 403), ("anonymous", 401)])
def test_technician_and_anonymous_are_refused(who, expected, technician_a, org_a):
    job = make_job(org_a)
    client = client_for(technician_a) if who == "technician" else APIClient()
    calls = [
        client.get("/api/jobs/"),
        client.get(f"/api/jobs/{job.pk}/"),
        client.post("/api/jobs/", body(), format="json"),
        client.patch(f"/api/jobs/{job.pk}/", {"version": 1}, format="json"),
        client.post(f"/api/jobs/{job.pk}/cancel/", {"reason": "x"}, format="json"),
    ]
    assert [c.status_code for c in calls] == [expected] * 5
    job.refresh_from_db()
    assert (job.status, job.version) == ("unassigned", 1)


def test_head_can_do_everything_a_dispatcher_can(head_a, org_a):
    client = client_for(head_a)
    created = client.post("/api/jobs/", body(), format="json")
    assert created.status_code == 201
    job_id = created.json()["id"]
    assert (
        client.patch(
            f"/api/jobs/{job_id}/", {"version": 1, "title": "x"}, format="json"
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/jobs/{job_id}/cancel/", {"reason": "x"}, format="json"
        ).status_code
        == 200
    )


# ---- assign / unassign by hand ----------------------------------------------
def assign(user, job, technician, version=None):
    return client_for(user).post(
        f"/api/jobs/{job.pk}/assign/",
        {
            "technician_id": technician_of(technician).pk,
            "version": job.version if version is None else version,
        },
        format="json",
    )


def test_assign_an_unassigned_job(dispatcher_a, org_a, technician_a):
    job = make_job(org_a)
    response = assign(dispatcher_a, job, technician_a)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "assigned" and data["version"] == job.version + 1
    assert data["technician"]["id"] == technician_of(technician_a).pk
    assert [h["to_status"] for h in data["history"]] == ["assigned"]


def test_assign_with_a_stale_version_is_a_409(dispatcher_a, org_a, technician_a):
    job = make_job(org_a)
    response = assign(dispatcher_a, job, technician_a, version=job.version + 5)
    assert response.status_code == 409
    assert response.data["detail"].code == "stale_version"
    job.refresh_from_db()
    assert job.status == "unassigned"


def test_assign_without_a_location_is_a_409(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, geocode_status="failed", lat=None, lng=None)
    response = assign(dispatcher_a, job, technician_a)
    assert response.status_code == 409
    assert response.data["detail"].code == "location_required"


def test_assign_a_deactivated_technician_is_a_409(dispatcher_a, org_a, technician_a):
    technician_a.is_active = False
    technician_a.save()
    response = assign(dispatcher_a, make_job(org_a), technician_a)
    assert response.status_code == 409
    assert response.data["detail"].code == "technician_inactive"


def test_assign_an_already_assigned_job_is_a_409(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, status="assigned", technician=technician_of(technician_a))
    response = assign(dispatcher_a, job, technician_a)
    assert response.status_code == 409
    assert response.data["detail"].code == "illegal_transition"


def test_assign_another_organizations_technician_is_a_400(
    dispatcher_a, org_a, technician_b
):
    response = assign(dispatcher_a, make_job(org_a), technician_b)
    assert response.status_code == 400 and "technician_id" in response.json()


def test_unassign_an_assigned_job(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, status="assigned", technician=technician_of(technician_a))
    response = client_for(dispatcher_a).post(
        f"/api/jobs/{job.pk}/unassign/", {"version": job.version}, format="json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unassigned" and data["technician"] is None


def test_unassign_an_ongoing_job_is_a_409(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, status="ongoing", technician=technician_of(technician_a))
    response = client_for(dispatcher_a).post(
        f"/api/jobs/{job.pk}/unassign/", {"version": job.version}, format="json"
    )
    assert response.status_code == 409


# ---- address lookup, manual pin, retry --------------------------------------
def lookup(user, **data):
    return client_for(user).post("/api/geocode/lookup/", data, format="json")


def test_lookup_finds_an_address(dispatcher_a):
    response = lookup(dispatcher_a, address="1204 Congress Ave", postal_code="78701")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok" and data["lat"] and data["lng"]


def test_lookup_reports_not_found_as_failed_not_an_error(dispatcher_a):
    data = lookup(dispatcher_a, address="unfindable road", postal_code="78701").json()
    assert data == {"status": "failed", "lat": None, "lng": None, "label": ""}


def test_lookup_survives_a_provider_failure(dispatcher_a):
    response = lookup(dispatcher_a, address="boom street", postal_code="78701")
    assert response.status_code == 200 and response.json()["status"] == "failed"


def test_lookup_needs_something_to_look_up(dispatcher_a):
    assert lookup(dispatcher_a, address="", postal_code="").status_code == 400


def test_lookup_is_for_dispatchers_only(technician_a):
    assert lookup(technician_a, address="1 Main St").status_code == 403
    assert APIClient().post("/api/geocode/lookup/", {"address": "x"}).status_code == 401


def pin(user, job, lat=30.27, lng=-97.74, version=None):
    return client_for(user).post(
        f"/api/jobs/{job.pk}/location/",
        {
            "lat": lat,
            "lng": lng,
            "version": job.version if version is None else version,
        },
        format="json",
    )


def test_pin_fixes_a_job_whose_address_failed(dispatcher_a, org_a):
    job = make_job(org_a, geocode_status="failed", lat=None, lng=None)
    response = pin(dispatcher_a, job)
    assert response.status_code == 200
    data = response.json()
    assert data["geocode_status"] == "manual" and data["version"] == job.version + 1
    job.refresh_from_db()
    assert (job.lat, job.lng) == (30.27, -97.74)


def test_a_pinned_job_can_then_be_assigned(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, geocode_status="failed", lat=None, lng=None)
    pinned = pin(dispatcher_a, job).json()
    job.refresh_from_db()
    assert pinned["status"] == "unassigned"
    assert assign(dispatcher_a, job, technician_a).status_code == 200


@pytest.mark.parametrize(("lat", "lng"), [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_pin_rejects_impossible_coordinates(dispatcher_a, org_a, lat, lng):
    assert pin(dispatcher_a, make_job(org_a), lat=lat, lng=lng).status_code == 400


def test_pin_with_a_stale_version_is_a_409(dispatcher_a, org_a):
    job = make_job(org_a)
    response = pin(dispatcher_a, job, version=job.version + 3)
    assert response.status_code == 409
    assert response.data["detail"].code == "stale_version"


def test_pin_is_refused_once_the_job_is_planned(dispatcher_a, org_a, technician_a):
    job = make_job(org_a, status="assigned", technician=technician_of(technician_a))
    response = pin(dispatcher_a, job)
    assert response.status_code == 409
    assert response.data["detail"].code == "job_not_editable"


def retry(user, job, version=None):
    return client_for(user).post(
        f"/api/jobs/{job.pk}/retry-geocode/",
        {"version": job.version if version is None else version},
        format="json",
    )


def test_retry_geocode_recovers_a_failed_job(dispatcher_a, org_a):
    job = make_job(
        org_a, address="1 Main St", geocode_status="failed", lat=None, lng=None
    )
    data = retry(dispatcher_a, job).json()
    assert data["geocode_status"] == "ok"


def test_retry_geocode_can_fail_again_without_an_error(dispatcher_a, org_a):
    job = make_job(org_a, address="boom street")
    response = retry(dispatcher_a, job)
    assert response.status_code == 200
    assert response.json()["geocode_status"] == "failed"


def test_retry_geocode_with_a_stale_version_is_a_409(dispatcher_a, org_a):
    job = make_job(org_a)
    assert retry(dispatcher_a, job, version=job.version + 2).status_code == 409


def test_detail_has_coordinates_but_the_list_does_not(dispatcher_a, org_a):
    job = make_job(org_a, lat=30.1, lng=-97.5)
    client = client_for(dispatcher_a)
    detail = client.get(f"/api/jobs/{job.pk}/").json()
    assert (detail["lat"], detail["lng"]) == (30.1, -97.5)
    row = client.get("/api/jobs/").json()["results"][0]
    assert "lat" not in row and "lng" not in row
