"""Edits are part of a job's history, not only status changes (manual-test finding)."""

import pytest

from api.models import JobStatusHistory, Skill
from api.services import jobs as job_service

from .conftest import client_for, make_job, technician_of


def patch(user, job, data):
    job.refresh_from_db()
    return client_for(user).patch(
        f"/api/jobs/{job.pk}/", {"version": job.version, **data}, format="json"
    )


def edits(job):
    return list(JobStatusHistory.objects.filter(job=job, kind="edit").order_by("id"))


def test_an_edit_adds_one_history_row_with_old_and_new_values(dispatcher_a, org_a):
    job = make_job(org_a, description="Old text", priority="normal")
    response = patch(dispatcher_a, job, {"description": "New text", "priority": "high"})
    assert response.status_code == 200, response.content
    (row,) = edits(job)
    assert row.changes == {
        "description": ["Old text", "New text"],
        "priority": ["normal", "high"],
    }
    assert row.changed_by == dispatcher_a and row.source == "manual"
    assert (row.from_status, row.to_status) == ("unassigned", "unassigned")


def test_the_row_comes_back_with_the_job(dispatcher_a, org_a):
    job = make_job(org_a, title="Before")
    data = patch(dispatcher_a, job, {"title": "After"}).json()
    row = data["history"][-1]
    assert row["kind"] == "edit"
    assert row["changes"] == {"title": ["Before", "After"]}
    assert row["changed_by"]["id"] == dispatcher_a.pk


def test_saving_without_a_change_adds_nothing(dispatcher_a, org_a):
    job = make_job(org_a, title="Same")
    assert patch(dispatcher_a, job, {"title": "Same"}).status_code == 200
    assert edits(job) == []


def test_a_skill_change_lists_skill_names(dispatcher_a, org_a):
    job = make_job(org_a)
    electrical = Skill.objects.get(name="Electrical")
    patch(dispatcher_a, job, {"skill_ids": [electrical.pk]})
    (row,) = edits(job)
    assert row.changes == {"skills": [["HVAC"], ["Electrical"]]}


def test_changing_the_address_records_the_new_location(dispatcher_a, org_a):
    job = make_job(org_a, location_label="1 Main St, 78701")
    patch(dispatcher_a, job, {"address": "9 Elm St", "postal_code": "78702"})
    (row,) = edits(job)
    assert row.changes["address"] == ["1 Main St", "9 Elm St"]
    assert row.changes["location"][0] == "1 Main St, 78701"
    assert "9 Elm St" in row.changes["location"][1]


def test_an_edit_to_an_assigned_job_is_recorded_against_its_status(
    dispatcher_a, org_a, technician_a
):
    job = make_job(org_a, priority="normal")
    job_service.transition(
        job, "assigned", dispatcher_a, technician=technician_of(technician_a)
    )
    assert patch(dispatcher_a, job, {"priority": "high"}).status_code == 200
    (row,) = edits(job)
    assert (row.from_status, row.to_status) == ("assigned", "assigned")
    assert row.technician_id == technician_of(technician_a).pk


def test_a_refused_or_stale_edit_leaves_no_row(dispatcher_a, org_a, technician_a):
    job = make_job(org_a)
    stale = client_for(dispatcher_a).patch(
        f"/api/jobs/{job.pk}/", {"version": 99, "title": "x"}, format="json"
    )
    assert stale.status_code == 409
    job_service.transition(
        job, "assigned", dispatcher_a, technician=technician_of(technician_a)
    )
    refused = patch(dispatcher_a, job, {"address": "9 Elm St"})
    assert refused.status_code == 409
    assert edits(job) == []


def test_pinning_a_job_on_the_map_is_recorded(dispatcher_a, org_a):
    job = make_job(org_a, location_label="1 Main St, 78701")
    response = client_for(dispatcher_a).post(
        f"/api/jobs/{job.pk}/location/",
        {"lat": 30.3, "lng": -97.7, "version": job.version},
        format="json",
    )
    assert response.status_code == 200, response.content
    (row,) = edits(job)
    assert row.changes == {"location": ["1 Main St, 78701", "Pinned on the map"]}


def test_edit_rows_do_not_break_the_technicians_repeat_of_incomplete(
    dispatcher_a, org_a, technician_a
):
    technician = technician_of(technician_a)
    job = make_job(org_a)
    job_service.transition(job, "assigned", dispatcher_a, technician=technician)
    job_service.arrive_job(job=job, technician=technician, actor=technician_a)
    job_service.incomplete_job(
        job=job, technician=technician, actor=technician_a, reason="No answer"
    )
    assert patch(dispatcher_a, job, {"title": "Edited after"}).status_code == 200
    again = job_service.incomplete_job(
        job=job, technician=technician, actor=technician_a, reason="No answer"
    )
    assert again.status == "unassigned"  # the repeat is still answered, not refused


def test_history_stays_append_only_for_edit_rows(dispatcher_a, org_a):
    job = make_job(org_a, title="A")
    patch(dispatcher_a, job, {"title": "B"})
    (row,) = edits(job)
    row.reason = "tampered"
    with pytest.raises(ValueError):
        row.save()
    with pytest.raises(Exception):  # noqa: B017 - any refusal will do
        row.delete()
