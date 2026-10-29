"""One test per database constraint, plus the model guards."""

import datetime

import pytest
from django.db import IntegrityError, transaction

from api.models import JobStatusHistory

from .conftest import Role, make_job, make_user, technician_of

START = datetime.datetime(2026, 11, 2, 9, tzinfo=datetime.UTC)


@pytest.fixture
def tech(org_a, technician_a):
    return technician_of(technician_a)


def test_one_ongoing_job_per_technician(org_a, tech):  # inv 3
    make_job(org_a, status="ongoing", technician=tech, sequence_position=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status="ongoing", technician=tech, sequence_position=2)


def test_two_technicians_may_each_have_an_ongoing_job(org_a, technician_a):
    other = make_user(org_a, Role.TECHNICIAN, "tech2@example.com")
    make_job(org_a, status="ongoing", technician=technician_of(technician_a))
    make_job(org_a, status="ongoing", technician=technician_of(other))


def test_duplicate_stop_for_same_technician_and_day(org_a, tech):
    make_job(org_a, status="assigned", technician=tech, sequence_position=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status="assigned", technician=tech, sequence_position=1)


def test_a_finished_stop_does_not_block_its_position(org_a, tech):
    make_job(org_a, status="completed", technician=tech, sequence_position=1)
    make_job(org_a, status="assigned", technician=tech, sequence_position=1)


def test_unassigned_jobs_may_share_null_positions(org_a):
    make_job(org_a)
    make_job(org_a)


def test_assigned_needs_a_technician(org_a):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status="assigned")


def test_ongoing_needs_a_technician(org_a):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status="ongoing")


def test_unassigned_has_no_technician(org_a, tech):  # inv 1
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status="unassigned", technician=tech)


def test_non_urgent_job_needs_a_slot(org_a):  # inv 7
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, slot_start=None, slot_end=None)


def test_urgent_job_may_have_no_slot(org_a):
    make_job(org_a, is_urgent=True, slot_start=None, slot_end=None)


def test_slot_must_end_after_it_starts(org_a):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, slot_start=START, slot_end=START)


@pytest.mark.parametrize("geocode_status", ["pending", "failed"])
@pytest.mark.parametrize("status", ["assigned", "ongoing"])
def test_no_assignment_without_a_location(
    org_a, tech, status, geocode_status
):  # inv 16
    with pytest.raises(IntegrityError), transaction.atomic():
        make_job(org_a, status=status, technician=tech, geocode_status=geocode_status)


@pytest.mark.parametrize("geocode_status", ["ok", "approximate", "manual"])
def test_assignment_allowed_with_a_usable_location(org_a, tech, geocode_status):
    make_job(org_a, status="assigned", technician=tech, geocode_status=geocode_status)


def test_technician_from_another_organization_is_rejected(
    org_a, technician_b
):  # inv 24
    with pytest.raises(ValueError, match="another organization"):
        make_job(org_a, status="assigned", technician=technician_of(technician_b))


# ---- history is append-only (invariant 15) ----------------------------------
@pytest.fixture
def row(org_a):
    job = make_job(org_a)
    return JobStatusHistory.objects.create(
        organization=org_a, job=job, from_status="", to_status="unassigned"
    )


def test_history_row_cannot_be_saved_again(row):
    row.reason = "edited"
    with pytest.raises(ValueError, match="append-only"):
        row.save()


def test_history_row_cannot_be_deleted(row):
    with pytest.raises(ValueError, match="append-only"):
        row.delete()


def test_history_queryset_cannot_update_or_delete(row):
    with pytest.raises(ValueError, match="append-only"):
        JobStatusHistory.objects.all().update(reason="x")
    with pytest.raises(ValueError, match="append-only"):
        JobStatusHistory.objects.all().delete()
    assert JobStatusHistory.objects.count() == 1


def test_job_with_history_cannot_be_deleted(row):
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        row.job.delete()
