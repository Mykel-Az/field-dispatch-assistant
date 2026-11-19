"""S2-10: the organization's clock decides a job's day, and the zone cannot change
while jobs are planned or under way (ADR-024)."""

import datetime

import pytest

from api.models import Job, JobStatus, Organization
from api.services import jobs as job_service

from .conftest import Role, client_for, make_job, make_user, technician_of

JOB = {
    "title": "Late call",
    "customer_name": "Ada",
    "category": "hvac",
    "address": "1 Main St",
    "postal_code": "78701",
}


def create(client, start, end):
    return client.post(
        "/api/jobs/",
        {**JOB, "slot_start": start, "slot_end": end},
        format="json",
    )


def set_zone(org, zone):
    Organization.objects.filter(pk=org.pk).update(timezone=zone)
    org.refresh_from_db()


def patch_org(head, version, **fields):
    return client_for(head).patch(
        "/api/organization/", {"version": version, **fields}, format="json"
    )


# ---- a job near midnight lands on the organization's local date ------------------
@pytest.mark.parametrize(
    ("zone", "start_utc", "local_date"),
    [
        # Behind UTC (Chicago, CST = UTC-6): 05:30Z on 3 Nov is 23:30 on 2 Nov there...
        ("America/Chicago", "2026-11-03T05:30:00Z", "2026-11-02"),
        # ...and 06:30Z is 00:30 on 3 Nov. The minute either side of local midnight.
        ("America/Chicago", "2026-11-03T06:30:00Z", "2026-11-03"),
        # Ahead of UTC (Auckland, NZDT = UTC+13): 11:30Z on 2 Nov is 00:30 on 3 Nov...
        ("Pacific/Auckland", "2026-11-02T11:30:00Z", "2026-11-03"),
        # ...and 10:30Z is 23:30 on 2 Nov. A UTC date would say 2 Nov for both.
        ("Pacific/Auckland", "2026-11-02T10:30:00Z", "2026-11-02"),
    ],
)
def test_a_job_near_midnight_gets_the_local_date(
    dispatcher_a, org_a, zone, start_utc, local_date
):
    set_zone(org_a, zone)
    start = datetime.datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    end = start + datetime.timedelta(hours=1)
    response = create(client_for(dispatcher_a), start.isoformat(), end.isoformat())
    assert response.status_code == 201
    assert response.json()["scheduled_date"] == local_date


def test_moving_a_slot_across_local_midnight_moves_the_date(dispatcher_a, org_a):
    set_zone(org_a, "America/Chicago")
    job = make_job(
        org_a,
        slot_start=datetime.datetime(
            2026, 11, 3, 4, tzinfo=datetime.UTC
        ),  # 22:00 on 2 Nov
        slot_end=datetime.datetime(2026, 11, 3, 5, tzinfo=datetime.UTC),
        scheduled_date=datetime.date(2026, 11, 2),
    )
    response = client_for(dispatcher_a).patch(
        f"/api/jobs/{job.pk}/",
        {
            "version": job.version,
            "slot_start": "2026-11-03T07:00:00Z",  # 01:00 on 3 Nov
            "slot_end": "2026-11-03T08:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["scheduled_date"] == "2026-11-03"


def test_an_urgent_job_is_for_today_on_the_organizations_clock(
    dispatcher_a, org_a, monkeypatch
):
    set_zone(org_a, "America/Chicago")
    # 05:50Z on 3 Nov: still 23:50 on 2 Nov in Chicago, already 3 Nov in UTC.
    monkeypatch.setattr(
        job_service.timezone,
        "now",
        lambda: datetime.datetime(2026, 11, 3, 5, 50, tzinfo=datetime.UTC),
    )
    response = client_for(dispatcher_a).post(
        "/api/jobs/", {**JOB, "is_urgent": True}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["scheduled_date"] == "2026-11-02"


# ---- the zone cannot change while jobs are Assigned or Ongoing ---------------------
@pytest.fixture
def tech(org_a):
    return technician_of(make_user(org_a, Role.TECHNICIAN, "tech-a@example.com"))


def live_job(org, tech, actor, status):
    job = make_job(org)
    job_service.transition(job, "assigned", actor, technician=tech)
    if status == JobStatus.ONGOING:
        job_service.transition(job, "ongoing", actor)
    return Job.objects.get(pk=job.pk)


@pytest.mark.parametrize("status", [JobStatus.ASSIGNED, JobStatus.ONGOING])
def test_the_zone_cannot_change_while_a_job_is_assigned_or_ongoing(
    head_a, dispatcher_a, org_a, tech, status
):
    live_job(org_a, tech, dispatcher_a, status)
    response = patch_org(head_a, 1, timezone="Pacific/Honolulu")
    assert response.status_code == 409
    assert response.data["detail"].code == "timezone_locked"
    assert "1 job is assigned or in progress" in response.data["detail"]
    org_a.refresh_from_db()
    assert (
        org_a.timezone == "America/Chicago" and org_a.version == 1
    )  # nothing was saved


def test_the_message_counts_the_jobs(head_a, dispatcher_a, org_a, tech):
    live_job(org_a, tech, dispatcher_a, JobStatus.ASSIGNED)
    live_job(org_a, tech, dispatcher_a, JobStatus.ASSIGNED)
    response = patch_org(head_a, 1, timezone="Pacific/Honolulu")
    assert "2 jobs are assigned or in progress" in response.data["detail"]


def test_a_blocked_zone_change_saves_none_of_the_other_fields_in_the_same_request(
    head_a, dispatcher_a, org_a, tech
):
    live_job(org_a, tech, dispatcher_a, JobStatus.ASSIGNED)
    response = patch_org(head_a, 1, timezone="Pacific/Honolulu", name="Renamed")
    assert response.status_code == 409
    org_a.refresh_from_db()
    assert org_a.name == "Org A" and org_a.timezone == "America/Chicago"


def test_the_zone_can_change_once_the_jobs_are_unassigned(
    head_a, dispatcher_a, org_a, tech
):
    job = live_job(org_a, tech, dispatcher_a, JobStatus.ASSIGNED)
    assert patch_org(head_a, 1, timezone="Pacific/Honolulu").status_code == 409
    job_service.transition(job, "unassigned", dispatcher_a)
    assert patch_org(head_a, 1, timezone="Pacific/Honolulu").status_code == 200


@pytest.mark.parametrize("final", ["unassigned", "completed", "canceled", "incomplete"])
def test_jobs_that_are_not_live_do_not_block_the_zone(
    head_a, dispatcher_a, org_a, tech, final
):
    job = make_job(org_a)
    if final != "unassigned":
        Job.objects.filter(pk=job.pk).update(
            status=final,
            technician=tech if final in ("completed", "incomplete") else None,
        )
    assert patch_org(head_a, 1, timezone="Pacific/Honolulu").status_code == 200


def test_an_empty_organization_can_change_its_zone(head_a):
    assert patch_org(head_a, 1, timezone="Pacific/Honolulu").status_code == 200


def test_other_settings_can_change_while_jobs_are_live(
    head_a, dispatcher_a, org_a, tech
):
    live_job(org_a, tech, dispatcher_a, JobStatus.ONGOING)
    ok = patch_org(
        head_a, 1, name="Renamed", work_start="07:00:00", work_end="18:00:00"
    )
    assert ok.status_code == 200 and ok.json()["name"] == "Renamed"


def test_sending_the_same_zone_again_is_not_a_change(head_a, dispatcher_a, org_a, tech):
    live_job(org_a, tech, dispatcher_a, JobStatus.ASSIGNED)
    assert (
        patch_org(head_a, 1, timezone="America/Chicago", name="Renamed").status_code
        == 200
    )


def test_another_organizations_jobs_do_not_block_this_one(
    head_a, org_b, dispatcher_a, tech
):
    other = technician_of(make_user(org_b, Role.TECHNICIAN, "tech-b@example.com"))
    other_dispatcher = make_user(org_b, Role.DISPATCHER, "disp-b@example.com")
    live_job(org_b, other, other_dispatcher, JobStatus.ASSIGNED)
    assert patch_org(head_a, 1, timezone="Pacific/Honolulu").status_code == 200


def test_a_dispatcher_still_cannot_change_the_zone_at_all(dispatcher_a):
    assert patch_org(dispatcher_a, 1, timezone="Pacific/Honolulu").status_code == 403
