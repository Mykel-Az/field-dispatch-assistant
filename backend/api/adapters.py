"""Django rows in, engine views out (ADR-006, ADR-019).

The only place that knows both worlds. It reads models and builds the frozen
views the pure `dispatch_engine` understands; it never writes to the database.
Callers prefetch (`technician.user`, `skills`, `acceptable_skills`) so these
functions cost no extra queries.

Data rule (ADR-019): the engine gets a job's title as its label and its
coordinates. Never the customer's name, phone or address.
"""

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dispatch_engine.distance import DEFAULT_SPEED_MPH
from dispatch_engine.types import JobView, Location, OrgConfig, Priority, TechView

from .models import Job, JobStatus, Organization, Technician

# TIME shortcut: these two belong on Organization too, so each business can tune
# them. Until then every organization shares the same values. (The daily job
# limit already lives on Organization, ADR-022.)
URGENT_BUFFER_MINUTES = 60.0
AT_RISK_MINUTES = 30.0


class OrganizationNotConfigured(ValueError):
    """The organization has no usable workstation or working hours yet."""


class JobNotLocated(ValueError):
    """The job has no coordinates, so the engine cannot plan it (invariant 16)."""


def _location(row) -> Location:
    return Location(lat=row.lat, lng=row.lng)


def at_local(day: date, clock: time, tz_name: str) -> datetime:
    """`clock` on `day`, read on the clock of `tz_name`, as an aware datetime."""
    return datetime.combine(day, clock, tzinfo=ZoneInfo(tz_name))


def org_to_config(organization: Organization) -> OrgConfig:
    if not organization.is_configured:
        raise OrganizationNotConfigured(
            "Set the organization's location and working hours before planning."
        )
    return OrgConfig(
        workstation=_location(organization),
        scoring_strategy=organization.scoring_strategy,
        speed_mph=DEFAULT_SPEED_MPH,
        urgent_buffer_minutes=URGENT_BUFFER_MINUTES,
        at_risk_minutes=AT_RISK_MINUTES,
        max_jobs_per_tech_per_day=organization.max_jobs_per_tech_per_day,
    )


def job_to_view(job: Job) -> JobView:
    if job.lat is None or job.lng is None:
        raise JobNotLocated(f"job {job.pk} has no coordinates")
    return JobView(
        id=job.pk,
        label=job.title,
        location=_location(job),
        is_urgent=job.is_urgent,
        created_at=job.created_at,
        slot_start=job.slot_start,
        slot_end=job.slot_end,
        duration_minutes=job.estimated_duration_minutes,
        acceptable_skill_ids=frozenset(s.pk for s in job.acceptable_skills.all()),
        # Stage 1 (ADR-020/021) adds Job.priority and Job.slot_is_fixed; until
        # then every job is normal priority with a fixed window.
        priority=Priority.NORMAL,
        slot_is_fixed=True,
    )


def _busy_until(job: Job) -> datetime | None:
    """When a job already on a technician's day ends, if we can tell."""
    started = (
        job.arrived_at if job.status == JobStatus.ONGOING else job.estimated_arrival
    )
    if started is None:
        return None
    return started + timedelta(minutes=job.estimated_duration_minutes)


def technician_to_view(
    technician: Technician,
    *,
    plan_date: date,
    organization: Organization,
    workload: Iterable[Job],
    now: datetime,
) -> TechView:
    """A technician as the engine sees them on `plan_date`.

    `workload` is their Assigned and Ongoing jobs for that day. TIME shortcut:
    those jobs only push `free_at` and `position` forward; they are not fixed
    anchors the new jobs can fit around.
    """
    tz = organization.timezone
    jobs = list(workload)
    free_at, position = now, _location(organization)
    for job in jobs:
        end = _busy_until(job)
        if end is not None and end > free_at and job.lat is not None:
            free_at, position = end, _location(job)
    user = technician.user
    return TechView(
        id=technician.pk,
        label=user.full_name or user.email,
        skill_ids=frozenset(s.pk for s in technician.skills.all()),
        shift_start=at_local(plan_date, technician.shift_start, tz),
        shift_end=at_local(plan_date, technician.shift_end, tz),
        is_available=user.is_active,
        free_at=free_at,
        position=position,
        assigned_count=len(jobs),
    )
