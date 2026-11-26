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
from dispatch_engine.types import (
    Commitment,
    JobView,
    Location,
    OrgConfig,
    Priority,
    TechView,
)

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


def _busy_chain(
    workload: Iterable[Job], now: datetime
) -> list[tuple[datetime, datetime, Job]]:
    """The stretches of a technician's day that are already taken, in the order they happen.

    Jobs are walked in the order they will happen: Ongoing first, then Assigned ones
    by their expected start. An Assigned job cannot start before the one before it
    ends, or before now, so two jobs assigned by hand do not both start "now". Each
    entry is (start, end, job). A job whose time has passed and whose window is shut
    holds nobody and is left out.
    """
    ordered = sorted(
        workload,
        key=lambda j: (
            j.status != JobStatus.ONGOING,
            _planned_start(j) or now,
            j.pk,
        ),
    )
    cursor = now
    chain: list[tuple[datetime, datetime, Job]] = []
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
        cursor = max(cursor, end)
        chain.append((start, end, job))
    return chain


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
    planner. Each is a fixed commitment: new jobs fit in the gaps between them, never
    moving them (ADR-027). `free_at` and `position` are where the technician is after
    the last one. TIME: a commitment's start is its planned arrival, else the start of
    the customer's window, else now; a job with neither blocks from now.
    """
    tz = organization.timezone
    jobs = list(workload)
    chain = _busy_chain(jobs, now)
    home = _location(organization)

    def where(job: Job) -> Location:
        return _location(job) if job.lat is not None else home

    free_at = max((end for _, end, _ in chain), default=now)
    last = max(chain, key=lambda c: c[1])[2] if chain else None
    position = where(last) if last is not None else home
    commitments = tuple(Commitment(start, end, where(job)) for start, end, job in chain)
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
        commitments=commitments,
        home=home,
    )
