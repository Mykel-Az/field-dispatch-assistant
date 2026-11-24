"""All writes to jobs. Nothing else may write Job.status (ADR-008)."""

import datetime
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from dispatch_engine import lifecycle as lc

from ..exceptions import Conflict
from ..models import (
    GeocodeStatus,
    Job,
    JobStatus,
    JobStatusHistory,
    Skill,
    Technician,
)
from ..versioning import check_and_bump_version
from .locations import locate


class JobError(Exception):
    """Base class. `code` is what the API puts in the response."""

    code = "error"


class IllegalJobTransition(JobError):
    code = "illegal_transition"


class ReasonRequired(JobError):
    code = "reason_required"


class JobNotEditable(JobError):
    code = "job_not_editable"


class AnotherJobOngoing(JobError):
    code = "another_job_ongoing"  # invariant 3: one Ongoing job per technician


class NotYourJob(JobError):
    """The job is not this technician's (the API answers 404, never "forbidden")."""

    code = "not_found"


class LocationRequired(JobError):
    code = "location_required"  # invariant 16


# Fields that change the plan. Once a job is assigned they are locked, because
# editing them would invalidate the technician's route (replanning on edit is
# out of scope: TIME). Everything else stays editable.
PLAN_FIELDS = (
    "is_urgent",
    "address",
    "postal_code",
    "slot_start",
    "slot_end",
    "scheduled_date",
    "slot_is_fixed",
    "estimated_duration_minutes",
)


def default_skills_for(category):
    """Skills a job of this category may be done by (CandidateSkillRule)."""
    return list(
        Skill.objects.filter(category_rules__category=category).order_by("name")
    )


def _record(job, *, from_status, actor, reason, technician_id, source="manual"):
    JobStatusHistory.objects.create(
        organization_id=job.organization_id,
        job=job,
        from_status=from_status,
        to_status=job.status,
        technician_id=technician_id,
        changed_by=actor,
        reason=reason,
        source=source,
    )


def _plain(value):
    """A field value as JSON can hold it (dates become ISO text)."""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _record_edit(job, *, actor, changes):
    """One history row saying what an edit changed. No row when nothing changed."""
    if not changes:
        return
    JobStatusHistory.objects.create(
        organization_id=job.organization_id,
        job=job,
        from_status=job.status,
        to_status=job.status,
        technician_id=job.technician_id,
        changed_by=actor,
        kind="edit",
        changes=changes,
    )


def local_date(moment, tz_name):
    """The calendar date of `moment` on the clock of `tz_name`.
    `moment=None` (an urgent job) means today there."""
    zone = ZoneInfo(tz_name)
    return (moment or timezone.now()).astimezone(zone).date()


class OpeningHoursMissing(ValueError):
    """A job for any time that day needs opening hours to mean anything."""


def opening_window(organization, day):
    """The organization's opening hours on `day`, as aware datetimes.

    This is the window of an "any time that day" job (ADR-021): the customer
    agreed to the day, not to a time, so the planner may use any of the hours the
    business is open.
    """
    if organization.work_start is None or organization.work_end is None:
        raise OpeningHoursMissing("Set the opening hours in Organization first.")
    zone = ZoneInfo(organization.timezone)
    return (
        datetime.datetime.combine(day, organization.work_start, tzinfo=zone),
        datetime.datetime.combine(day, organization.work_end, tzinfo=zone),
    )


def rederive_dates(organization):
    """After the organization's time zone or opening hours change.

    A job with an agreed time moves to the day that time falls on in the new
    zone. An "any time that day" job keeps its day, the day being what was agreed,
    and, while it is still unassigned, takes the new opening hours as its window.
    A planned one keeps the window it was planned in. Urgent jobs keep their day.
    """
    changed = 0
    for job in Job.objects.filter(organization=organization, slot_start__isnull=False):
        if not job.slot_is_fixed:
            if job.status == JobStatus.UNASSIGNED and job.scheduled_date:
                start, end = opening_window(organization, job.scheduled_date)
                if (start, end) != (job.slot_start, job.slot_end):
                    Job.objects.filter(pk=job.pk).update(slot_start=start, slot_end=end)
                    changed += 1
            continue
        day = local_date(job.slot_start, organization.timezone)
        if day != job.scheduled_date:
            Job.objects.filter(pk=job.pk).update(scheduled_date=day)
            changed += 1
    return changed


def _plan_field_lock(job, client_version):
    """Lock the job for a location change: right version, still unassigned."""
    locked = Job.objects.select_for_update().get(pk=job.pk)
    check_and_bump_version(locked, client_version)
    if locked.status != JobStatus.UNASSIGNED:
        raise JobNotEditable
    return locked


def pin_job(*, job, lat, lng, client_version, actor=None):
    """The dispatcher placed the job on the map by hand."""
    with transaction.atomic():
        locked = _plan_field_lock(job, client_version)
        before = locked.location_label
        locked.lat, locked.lng = lat, lng
        locked.geocode_status = GeocodeStatus.MANUAL
        locked.location_label = "Pinned on the map"
        locked.save()
        _record_edit(
            locked, actor=actor, changes={"location": [before, locked.location_label]}
        )
    return locked


def retry_geocode(*, job, client_version, actor=None):
    """Look the stored address up again (the provider may have been down)."""
    probe = Job(address=job.address, postal_code=job.postal_code)
    locate(probe)  # network call: outside the transaction
    with transaction.atomic():
        locked = _plan_field_lock(job, client_version)
        before = locked.location_label
        locked.lat, locked.lng = probe.lat, probe.lng
        locked.geocode_status = probe.geocode_status
        locked.location_label = probe.location_label
        locked.save()
        _record_edit(
            locked,
            actor=actor,
            changes={"location": [before, locked.location_label]}
            if before != locked.location_label
            else {},
        )
    return locked


def create_job(*, organization, actor, skills, **fields):
    """Create a job in `organization`, geocode it, write its first history row."""
    job = Job(organization=organization, **fields)
    locate(job)  # network call: outside the transaction
    with transaction.atomic():
        job.save()
        job.acceptable_skills.set(skills)
        _record(job, from_status="", actor=actor, reason="", technician_id=None)
    return job


def update_job(*, job, client_version, skills=None, actor=None, **changes):
    """Edit a job under a row lock. 409 if the version is stale or the job is
    already planned and a plan field would change."""
    address_changed = any(
        k in changes and changes[k] != getattr(job, k)
        for k in ("address", "postal_code")
    )
    geocoded = None
    if address_changed:
        probe = Job(
            address=changes.get("address", job.address),
            postal_code=changes.get("postal_code", job.postal_code),
        )
        geocoded = locate(probe)  # network call: outside the transaction

    with transaction.atomic():
        locked = Job.objects.select_for_update().get(pk=job.pk)
        check_and_bump_version(locked, client_version)

        plan_edit = any(
            k in changes and changes[k] != getattr(locked, k) for k in PLAN_FIELDS
        )
        if skills is not None:
            plan_edit = plan_edit or {s.pk for s in skills} != set(
                locked.acceptable_skills.values_list("pk", flat=True)
            )
        if plan_edit and locked.status != JobStatus.UNASSIGNED:
            raise JobNotEditable

        diff = {
            field: [_plain(getattr(locked, field)), _plain(value)]
            for field, value in changes.items()
            if getattr(locked, field) != value
        }
        for field, value in changes.items():
            setattr(locked, field, value)
        if geocoded is not None:
            if geocoded.location_label != locked.location_label:
                diff["location"] = [locked.location_label, geocoded.location_label]
            locked.lat, locked.lng = geocoded.lat, geocoded.lng
            locked.geocode_status = geocoded.geocode_status
            locked.location_label = geocoded.location_label
        locked.save()
        if skills is not None:
            before = sorted(locked.acceptable_skills.values_list("name", flat=True))
            after = sorted(s.name for s in skills)
            if before != after:
                diff["skills"] = [before, after]
            locked.acceptable_skills.set(skills)
        _record_edit(locked, actor=actor, changes=diff)
    return locked


def transition(
    job, to, actor, reason="", *, technician=None, client_version=None, source="manual"
):
    """The only place a job's status changes.

    Checks the lifecycle table, updates the job and writes exactly one history
    row, all in one transaction. Returns the fresh, locked job. `technician` is
    required when moving to Assigned (the database insists on it). When
    `client_version` is given (a person acting on a screen), it must still be the
    job's current version, otherwise 409 stale_version. `source` is "planner" when
    the planner made the change on behalf of `actor`, who ran it.
    """
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(pk=job.pk)
        if client_version is not None and client_version != locked.version:
            raise Conflict(
                "This job was changed by someone else. Reload it.",
                code="stale_version",
            )
        src = locked.status
        try:
            lc.JobLifecycleEngine.check_transition(src, to)
        except lc.IllegalTransition as exc:
            raise IllegalJobTransition(str(exc)) from exc
        if to in lc.REASON_REQUIRED and not reason.strip():
            raise ReasonRequired(f"a reason is required to move to {to}")
        if to == lc.ASSIGNED:
            if technician is None:
                raise ValueError("moving to assigned needs a technician")
            if locked.geocode_status not in ("ok", "approximate", "manual"):
                raise LocationRequired("the job has no usable location yet")

        involved = technician.pk if technician else locked.technician_id
        locked.status = to
        if to == lc.ASSIGNED:
            locked.technician = technician
        if to in (lc.UNASSIGNED, lc.CANCELED):
            # Back to the queue, or dead: let go of the technician and the stop.
            locked.technician = None
            locked.sequence_position = None
            locked.estimated_arrival = None
        if to in (lc.ASSIGNED, lc.UNASSIGNED, lc.CANCELED):
            # An old "why" must not outlive the decision it explained. The planner
            # writes the new one right after it assigns.
            locked.plan_explanation = None
        now = timezone.now()
        if to == lc.ONGOING:
            locked.arrived_at = now
        if to in (lc.COMPLETED, lc.INCOMPLETE, lc.FAILED):
            locked.completed_at = now
        locked.version += 1
        locked.save()
        _record(
            locked,
            from_status=src,
            actor=actor,
            reason=reason,
            technician_id=involved,
            source=source,
        )
    return locked


def cancel_job(*, job, actor, reason):
    """Cancel a job. Idempotent: an already-canceled job is returned untouched."""
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(pk=job.pk)
        if locked.status == JobStatus.CANCELED:
            return locked
        return transition(locked, lc.CANCELED, actor, reason)


@transaction.atomic
def release_assigned_jobs(technician, actor):
    """Send a technician's Assigned jobs back to the queue (e.g. on deactivation).

    A named exception to the frozen-job rule (invariant 12). Ongoing jobs are
    never touched. Rows are locked in id order so two releases cannot deadlock.
    """
    jobs = list(
        Job.objects.select_for_update()
        .filter(technician=technician, status=JobStatus.ASSIGNED)
        .order_by("id")
    )
    for job in jobs:
        transition(job, lc.UNASSIGNED, actor, "technician deactivated")
    return len(jobs)


# ---- the technician's three actions (S2-7) -----------------------------------
# Each one is safe to repeat: a second tap, a retry after a dropped connection or two
# open tabs answer 200 with the job as it now is, instead of an error. They lock the
# technician's row first, then the job's, so two requests for the same technician take
# turns (a second Arrive cannot slip in beside the first); the database's one-Ongoing-
# job constraint is the backstop. Reasons for a wrong state: IllegalJobTransition.


def _lock(job, technician):
    Technician.objects.select_for_update().get(pk=technician.pk)
    return Job.objects.select_for_update().get(pk=job.pk)


def _owns(job, technician):
    return job.technician_id == technician.pk


def arrive_job(*, job, technician, actor):
    """Assigned -> Ongoing. Already Ongoing: nothing to do. Another Ongoing job: refused."""
    try:
        with transaction.atomic():
            locked = _lock(job, technician)
            if not _owns(locked, technician):
                raise NotYourJob
            if locked.status == JobStatus.ONGOING:
                return locked
            if (
                Job.objects.filter(technician=technician, status=JobStatus.ONGOING)
                .exclude(pk=locked.pk)
                .exists()
            ):
                raise AnotherJobOngoing("Finish your current job first.")
            return transition(locked, lc.ONGOING, actor)
    except IntegrityError:  # the constraint caught what the check could not
        raise AnotherJobOngoing("Finish your current job first.") from None


def complete_job(*, job, technician, actor):
    """Ongoing -> Completed. Already Completed: nothing to do."""
    with transaction.atomic():
        locked = _lock(job, technician)
        if not _owns(locked, technician):
            raise NotYourJob
        if locked.status == JobStatus.COMPLETED:
            return locked
        return transition(locked, lc.COMPLETED, actor)


def _returned_by(job, technician):
    """True when this technician already marked the job incomplete and it went back
    to the queue and nothing has happened to it since (the repeat of a finished action)."""
    last_two = list(job.history.filter(kind="status").order_by("-id")[:2])
    return (
        job.status == JobStatus.UNASSIGNED
        and len(last_two) == 2
        and last_two[0].from_status == lc.INCOMPLETE
        and last_two[0].to_status == lc.UNASSIGNED
        and last_two[1].to_status == lc.INCOMPLETE
        and last_two[1].technician_id == technician.pk
    )


def incomplete_job(*, job, technician, actor, reason):
    """Ongoing -> Incomplete (with a reason) and straight back to the queue.

    Two history rows, so the story reads: could not finish (why), then back in the
    queue. Repeating it once the job is back in the queue answers with that job.
    """
    with transaction.atomic():
        locked = _lock(job, technician)
        if not _owns(locked, technician):
            if _returned_by(locked, technician):
                return locked
            raise NotYourJob
        marked = transition(locked, lc.INCOMPLETE, actor, reason)
        Job.objects.filter(pk=marked.pk).update(attempt_count=F("attempt_count") + 1)
        return transition(
            marked,
            lc.UNASSIGNED,
            actor,
            "Returned to the queue: the job was not finished.",
        )
