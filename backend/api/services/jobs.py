"""All writes to jobs. Nothing else may write Job.status (ADR-008)."""

from django.db import transaction
from django.utils import timezone

from dispatch_engine import lifecycle as lc

from ..exceptions import Conflict
from ..models import Job, JobStatus, JobStatusHistory, Skill
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
    "estimated_duration_minutes",
)


def default_skills_for(category):
    """Skills a job of this category may be done by (CandidateSkillRule)."""
    return list(
        Skill.objects.filter(category_rules__category=category).order_by("name")
    )


def _record(job, *, from_status, actor, reason, technician_id):
    JobStatusHistory.objects.create(
        organization_id=job.organization_id,
        job=job,
        from_status=from_status,
        to_status=job.status,
        technician_id=technician_id,
        changed_by=actor,
        reason=reason,
    )


def create_job(*, organization, actor, skills, **fields):
    """Create a job in `organization`, geocode it, write its first history row."""
    job = Job(organization=organization, **fields)
    locate(job)  # network call: outside the transaction
    with transaction.atomic():
        job.save()
        job.acceptable_skills.set(skills)
        _record(job, from_status="", actor=actor, reason="", technician_id=None)
    return job


def update_job(*, job, client_version, skills=None, **changes):
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

        for field, value in changes.items():
            setattr(locked, field, value)
        if geocoded is not None:
            locked.lat, locked.lng = geocoded.lat, geocoded.lng
            locked.geocode_status = geocoded.geocode_status
            locked.location_label = geocoded.location_label
        locked.save()
        if skills is not None:
            locked.acceptable_skills.set(skills)
    return locked


def transition(job, to, actor, reason="", *, technician=None, client_version=None):
    """The only place a job's status changes.

    Checks the lifecycle table, updates the job and writes exactly one history
    row, all in one transaction. Returns the fresh, locked job. `technician` is
    required when moving to Assigned (the database insists on it). When
    `client_version` is given (a person acting on a screen), it must still be the
    job's current version, otherwise 409 stale_version.
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
        now = timezone.now()
        if to == lc.ONGOING:
            locked.arrived_at = now
        if to in (lc.COMPLETED, lc.INCOMPLETE, lc.FAILED):
            locked.completed_at = now
        locked.version += 1
        locked.save()
        _record(
            locked, from_status=src, actor=actor, reason=reason, technician_id=involved
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
