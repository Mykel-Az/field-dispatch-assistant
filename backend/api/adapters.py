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

from .models import Job, JobPriority, JobStatus, Organization, Technician

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


_PRIORITY = {
    JobPriority.LOW: Priority.LOW,
    JobPriority.NORMAL: Priority.NORMAL,
    JobPriority.HIGH: Priority.HIGH,
}


def job_to_view(job: Job, *, urgent_clock_start: datetime | None = None) -> JobView:
    """A job as the engine sees it.

    An urgent job's deadline is its creation time plus the urgent buffer. When the
    day being planned opens after that (an emergency logged tonight for tomorrow's
    first call), the buffer would already be spent before anyone could start, and
    every plan would read "1,500 minutes late". `urgent_clock_start` (the day's
    opening) moves the start of that clock forward so the buffer counts from the
    first moment someone can actually work.
    """
    if job.lat is None or job.lng is None:
        raise JobNotLocated(f"job {job.pk} has no coordinates")
    return JobView(
        id=job.pk,
        label=job.title,
        location=_location(job),
        is_urgent=job.is_urgent,
        created_at=(
            max(job.created_at, urgent_clock_start)
            if job.is_urgent and urgent_clock_start
            else job.created_at
        ),
        slot_start=job.slot_start,
        slot_end=job.slot_end,
        duration_minutes=job.estimated_duration_minutes,
        acceptable_skill_ids=frozenset(s.pk for s in job.acceptable_skills.all()),
        priority=_PRIORITY[job.priority],
        slot_is_fixed=job.slot_is_fixed,
    )


def _planned_start(job: Job) -> datetime | None:
    """When an Assigned job is expected to begin: the planner's arrival time, else the
    start of the customer's window (a job assigned by hand has no arrival time yet)."""
    return job.estimated_arrival or job.slot_start


def _busy_chain(workload: Iterable[Job], now: datetime) -> tuple[datetime, Job | None]:
    """When a technician finishes everything already on their day, and with which job.

    Jobs are walked in the order they will happen: Ongoing first, then Assigned ones
    by their expected start. An Assigned job cannot start before the one before it
    ends, or before now, so two jobs assigned by hand do not both start "now". The
    job a technician finishes last is where they will be.
    """
    ordered = sorted(
        workload,
        key=lambda j: (
            j.status != JobStatus.ONGOING,
            _planned_start(j) or now,
            j.pk,
        ),
    )
    cursor, last = now, None
    for job in ordered:
        duration = timedelta(minutes=job.estimated_duration_minutes)
        if job.status == JobStatus.ONGOING and job.arrived_at is not None:
            start = job.arrived_at
        else:
            planned = _planned_start(job)
            window_open = job.slot_end is not None and job.slot_end > now
            if planned is not None and planned + duration <= now and not window_open:
                continue  # its time has passed and its window is shut: not holding anyone
            start = max(cursor, planned or cursor)
        end = start + duration
        if end > cursor:
            cursor, last = end, job
    return cursor, last


def technician_to_view(
    technician: Technician,
    *,
    plan_date: date,
    organization: Organization,
    workload: Iterable[Job],
    now: datetime,
) -> TechView:
    """A technician as the engine sees them on `plan_date`.

    `workload` is their Assigned and Ongoing jobs for that day, by hand or by the
    planner. TIME shortcut: those jobs only push `free_at` and `position` forward
    (the technician is treated as busy until the last one ends); they are not fixed
    anchors the new jobs can fit around, so a gap before a later job is not used
    until gap insertion (S3c).
    """
    tz = organization.timezone
    jobs = list(workload)
    free_at, last = _busy_chain(jobs, now)
    position = (
        _location(last)
        if last is not None and last.lat is not None
        else _location(organization)
    )
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
