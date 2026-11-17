"""Stage 1 (ADR-020, ADR-021): job priority, and "any time that day" jobs."""

import datetime

import pytest
from django.db import IntegrityError, transaction

from api.models import Job

from .conftest import client_for, make_job, technician_of

UTC = datetime.UTC
SLOT = {"slot_start": "2026-11-02T09:00:00Z", "slot_end": "2026-11-02T11:00:00Z"}
DAY = "2026-11-02"


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


@pytest.fixture
def org(org_a):
    """Open 08:00-17:00 in Chicago, which is UTC-6 on 2 Nov 2026."""
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


def post(user, **overrides):
    return client_for(user).post("/api/jobs/", body(**overrides), format="json")


def patch(user, job, data):
    return client_for(user).patch(f"/api/jobs/{job.pk}/", data, format="json")


# ---- priority ----------------------------------------------------------------
def test_a_new_job_is_normal_priority_with_a_fixed_slot(dispatcher_a, org):
    data = post(dispatcher_a).json()
    assert (data["priority"], data["slot_is_fixed"]) == ("normal", True)


def test_priority_can_be_chosen_when_creating(dispatcher_a, org):
    assert post(dispatcher_a, priority="high").json()["priority"] == "high"
    assert post(dispatcher_a, priority="low").json()["priority"] == "low"


def test_an_unknown_priority_is_refused(dispatcher_a, org):
    response = post(dispatcher_a, priority="urgent-ish")
    assert response.status_code == 400 and "priority" in response.json()


def test_priority_and_slot_kind_are_in_the_list_and_the_detail(dispatcher_a, org):
    created = post(dispatcher_a, priority="high").json()
    client = client_for(dispatcher_a)
    [row] = client.get("/api/jobs/").json()["results"]
    detail = client.get(f"/api/jobs/{created['id']}/").json()
    for shown in (row, detail):
        assert (shown["priority"], shown["slot_is_fixed"]) == ("high", True)


def test_priority_can_change_after_the_job_is_assigned(dispatcher_a, org, technician_a):
    """It orders the next plan; it does not move a stop that is already planned."""
    tech = technician_of(technician_a)
    job = make_job(org, status="assigned", technician=tech, sequence_position=1)
    response = patch(dispatcher_a, job, {"version": 1, "priority": "high"})
    assert response.status_code == 200 and response.json()["priority"] == "high"
    job.refresh_from_db()
    assert (job.technician_id, job.sequence_position) == (tech.pk, 1)


# ---- any time that day -------------------------------------------------------
def test_any_time_that_day_takes_the_opening_hours_as_its_window(dispatcher_a, org):
    data = client_for(dispatcher_a).post(
        "/api/jobs/",
        {k: v for k, v in body(any_time_on=DAY).items() if not k.startswith("slot_")},
        format="json",
    )
    assert data.status_code == 201, data.content
    job = Job.objects.get(pk=data.json()["id"])
    assert job.slot_is_fixed is False
    assert job.slot_start == datetime.datetime(2026, 11, 2, 14, tzinfo=UTC)  # 08:00 CST
    assert job.slot_end == datetime.datetime(2026, 11, 2, 23, tzinfo=UTC)  # 17:00 CST
    assert job.scheduled_date == datetime.date(2026, 11, 2)
    assert data.json()["slot_is_fixed"] is False


def only_day(**extra):
    return {
        k: v
        for k, v in body(any_time_on=DAY, **extra).items()
        if not k.startswith("slot_")
    }


def test_a_day_and_a_time_window_together_are_refused(dispatcher_a, org):
    response = post(dispatcher_a, any_time_on=DAY)
    assert response.status_code == 400 and "any_time_on" in response.json()


def test_any_time_that_day_needs_opening_hours(dispatcher_a, org_a):
    response = client_for(dispatcher_a).post("/api/jobs/", only_day(), format="json")
    assert response.status_code == 400
    assert "opening hours" in str(response.json()["any_time_on"])


def test_an_urgent_job_does_not_take_a_day(dispatcher_a, org):
    response = client_for(dispatcher_a).post(
        "/api/jobs/", only_day(is_urgent=True), format="json"
    )
    assert response.status_code == 400 and "any_time_on" in response.json()


def test_a_client_cannot_say_a_slot_is_movable(dispatcher_a, org):
    """slot_is_fixed follows from how the time was entered, not from the request."""
    data = post(dispatcher_a, slot_is_fixed=False).json()
    assert data["slot_is_fixed"] is True


def test_slot_is_fixed_cannot_be_patched_directly(dispatcher_a, org):
    job = make_job(org)
    response = patch(dispatcher_a, job, {"version": 1, "slot_is_fixed": False})
    assert response.status_code == 400 and "slot_is_fixed" in response.json()


def test_an_agreed_time_can_become_any_time_and_back(dispatcher_a, org):
    job = make_job(org)
    flexible = patch(dispatcher_a, job, {"version": 1, "any_time_on": "2026-11-03"})
    assert flexible.status_code == 200, flexible.content
    job.refresh_from_db()
    assert job.slot_is_fixed is False
    assert job.scheduled_date == datetime.date(2026, 11, 3)
    assert job.slot_start == datetime.datetime(2026, 11, 3, 14, tzinfo=UTC)

    fixed = patch(dispatcher_a, job, {"version": 2, **SLOT})
    assert fixed.status_code == 200, fixed.content
    job.refresh_from_db()
    assert job.slot_is_fixed is True and job.scheduled_date == datetime.date(
        2026, 11, 2
    )


def test_editing_something_else_leaves_an_any_time_job_alone(dispatcher_a, org):
    job = make_job(
        org,
        slot_is_fixed=False,
        slot_start=datetime.datetime(2026, 11, 2, 14, tzinfo=UTC),
        slot_end=datetime.datetime(2026, 11, 2, 23, tzinfo=UTC),
    )
    assert (
        patch(dispatcher_a, job, {"version": 1, "title": "New title"}).status_code
        == 200
    )
    job.refresh_from_db()
    assert job.slot_is_fixed is False


def test_the_window_is_locked_once_assigned(dispatcher_a, org, technician_a):
    job = make_job(
        org,
        status="assigned",
        technician=technician_of(technician_a),
        sequence_position=1,
    )
    response = patch(dispatcher_a, job, {"version": 1, "any_time_on": DAY})
    assert response.status_code == 409


# ---- the window follows the opening hours ------------------------------------
def anytime(org, **fields):
    day = fields.pop("day", datetime.date(2026, 11, 2))
    return make_job(
        org,
        slot_is_fixed=False,
        scheduled_date=day,
        slot_start=datetime.datetime.combine(day, datetime.time(14), tzinfo=UTC),
        slot_end=datetime.datetime.combine(day, datetime.time(23), tzinfo=UTC),
        **fields,
    )


def org_patch(head, version, **data):
    response = client_for(head).patch(
        "/api/organization/", {"version": version, **data}, format="json"
    )
    assert response.status_code == 200, response.content


def test_new_opening_hours_move_the_window_of_unassigned_any_time_jobs(head_a, org):
    open_job = anytime(org)
    fixed_job = make_job(org)
    org_patch(head_a, org.version, work_start="09:00:00", work_end="18:00:00")
    open_job.refresh_from_db()
    fixed_job.refresh_from_db()
    assert open_job.slot_start == datetime.datetime(2026, 11, 2, 15, tzinfo=UTC)
    assert open_job.slot_end == datetime.datetime(2026, 11, 3, 0, tzinfo=UTC)
    assert fixed_job.slot_start == datetime.datetime(
        2026, 11, 2, 9, tzinfo=UTC
    )  # agreed time: untouched


def test_a_planned_any_time_job_keeps_the_window_it_was_planned_in(
    head_a, org, technician_a
):
    job = anytime(
        org,
        status="assigned",
        technician=technician_of(technician_a),
        sequence_position=1,
    )
    org_patch(head_a, org.version, work_start="09:00:00")
    job.refresh_from_db()
    assert job.slot_start == datetime.datetime(2026, 11, 2, 14, tzinfo=UTC)


def test_a_new_time_zone_keeps_an_any_time_job_on_its_day(head_a, org):
    job = anytime(org)
    org_patch(head_a, org.version, timezone="Pacific/Honolulu")  # UTC-10
    job.refresh_from_db()
    assert job.scheduled_date == datetime.date(2026, 11, 2)  # the day that was agreed
    assert job.slot_start == datetime.datetime(
        2026, 11, 2, 18, tzinfo=UTC
    )  # 08:00 in Honolulu


# ---- the database ------------------------------------------------------------
def test_the_database_refuses_an_any_time_job_without_a_window(org):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(
            org, slot_is_fixed=False, slot_start=None, slot_end=None, is_urgent=True
        )
