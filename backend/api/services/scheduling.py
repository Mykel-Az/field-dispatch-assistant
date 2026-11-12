"""Run the dispatch engine for one day and save the result (ADR-008).

The engine is pure: it reads views and returns a Plan. This module is the only
place that connects it to the database. It builds the views (`adapters`), runs
ASSIGN once, and then applies each assignment through `transition`, so the job
lifecycle, the history rows and the one-ongoing-job rule all still apply.
Everything happens in one transaction: a failure leaves no half-planned day.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from dispatch_engine import lifecycle as lc
from dispatch_engine.assignment import assign_jobs
from dispatch_engine.clock import Clock, FixedClock, SystemClock
from dispatch_engine.distance import HaversineProvider
from dispatch_engine.explanations import assignment_sentence, unassigned_sentence
from dispatch_engine.types import Explanation

from ..adapters import at_local, job_to_view, org_to_config, technician_to_view
from ..models import GeocodeStatus, Job, JobStatus, Organization, Technician
from .jobs import local_date, transition

USABLE_LOCATION = (GeocodeStatus.OK, GeocodeStatus.APPROXIMATE, GeocodeStatus.MANUAL)


@dataclass(frozen=True)
class PlannedJob:
    job_id: int
    technician_id: int
    estimated_arrival: datetime
    sla_label: str
    slack_minutes: float
    reasons: list[dict]
    sentence: str


@dataclass(frozen=True)
class UnplannedJob:
    job_id: int
    reasons: list[dict]
    sentence: str


@dataclass(frozen=True)
class SkippedJob:
    """Left out of the run entirely: the engine cannot plan a job without a location."""

    job_id: int
    code: str
    sentence: str


@dataclass(frozen=True)
class ScheduleResult:
    plan_date: date
    assigned: list[PlannedJob]
    unassigned: list[UnplannedJob]
    skipped: list[SkippedJob]


def reasons_as_data(explanation: Explanation) -> list[dict]:
    """The structured explanation as plain JSON: what is stored and returned."""
    return [{"code": str(r.code), "facts": dict(r.facts)} for r in explanation.reasons]


def generate_schedule(
    *,
    organization,
    actor,
    plan_date: date | None = None,
    clock: Clock | None = None,
) -> ScheduleResult:
    """Assign the organization's unassigned jobs for `plan_date` (default: today there).

    Safe to run twice: only unassigned jobs are touched, and jobs that are already
    assigned stay put (invariant 12); they only count as the technician's load.
    Raises `OrganizationNotConfigured` when the organization has no location or hours.
    """
    config = org_to_config(organization)
    now = (clock or SystemClock()).now()  # read once: the whole run uses this instant
    plan_date = plan_date or local_date(now, organization.timezone)
    distance = HaversineProvider(speed_mph=config.speed_mph)

    with transaction.atomic():
        # One planner run per organization at a time: a second run waits here, then
        # reads the loads the first one saved instead of planning from a stale picture.
        Organization.objects.select_for_update().get(pk=organization.pk)
        # Lock the candidate jobs too, in id order: no job can be claimed twice.
        candidates = list(
            Job.objects.for_organization(organization)
            .select_for_update()
            .filter(status=JobStatus.UNASSIGNED, scheduled_date=plan_date)
            .prefetch_related("acceptable_skills")
            .order_by("id")
        )
        plannable = [j for j in candidates if _is_located(j)]
        skipped = [_skipped(j) for j in candidates if not _is_located(j)]

        technicians = list(
            Technician.objects.for_organization(organization)
            .select_related("user")
            .prefetch_related("skills")
            .order_by("id")
        )
        workload = defaultdict(list)
        for job in Job.objects.for_organization(organization).filter(
            status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING],
            scheduled_date=plan_date,
            technician__isnull=False,
        ):
            workload[job.technician_id].append(job)

        day_opens = at_local(plan_date, organization.work_start, organization.timezone)
        job_views = {
            j.pk: job_to_view(j, urgent_clock_start=day_opens) for j in plannable
        }
        tech_views = {
            t.pk: technician_to_view(
                t,
                plan_date=plan_date,
                organization=organization,
                workload=workload[t.pk],
                now=now,
            )
            for t in technicians
        }

        plan = assign_jobs(
            job_views.values(), tech_views.values(), config, distance, FixedClock(now)
        )

        jobs = {j.pk: j for j in plannable}
        techs = {t.pk: t for t in technicians}
        next_position = _next_positions(organization, plan_date)
        assigned: list[PlannedJob] = []
        for a in plan.assignments:
            reasons = reasons_as_data(a.explanation)
            sentence = assignment_sentence(a, job_views[a.job_id], tech_views)
            saved = transition(
                jobs[a.job_id],
                lc.ASSIGNED,
                actor,
                technician=techs[a.technician_id],
            )
            saved.estimated_arrival = a.estimated_arrival
            saved.sequence_position = next_position[a.technician_id]
            saved.plan_explanation = {
                "reasons": reasons,
                "sentence": sentence,
                "sla_label": str(a.sla_label),
                "slack_minutes": a.slack_minutes,
            }
            saved.save(
                update_fields=[
                    "estimated_arrival",
                    "sequence_position",
                    "plan_explanation",
                    "updated_at",
                ]
            )
            next_position[a.technician_id] += 1
            assigned.append(
                PlannedJob(
                    a.job_id,
                    a.technician_id,
                    a.estimated_arrival,
                    str(a.sla_label),
                    a.slack_minutes,
                    reasons,
                    sentence,
                )
            )

        unassigned: list[UnplannedJob] = []
        for u in plan.unassigned:
            reasons = reasons_as_data(u.explanation)
            sentence = unassigned_sentence(u, job_views[u.job_id], tech_views)
            Job.objects.filter(pk=u.job_id).update(
                plan_explanation={"reasons": reasons, "sentence": sentence},
                updated_at=timezone.now(),
            )
            unassigned.append(UnplannedJob(u.job_id, reasons, sentence))

    return ScheduleResult(plan_date, assigned, unassigned, skipped)


def _skipped(job: Job) -> SkippedJob:
    return SkippedJob(
        job.pk,
        "needs_location",
        f"“{job.title}” has no usable location yet, so it was not planned.",
    )


def current_schedule(
    *, organization, plan_date: date | None = None, clock: Clock | None = None
) -> ScheduleResult:
    """What the planner last decided for `plan_date`, read back from the database.

    Same shape as `generate_schedule`, built from the stored explanations, so the
    plan page can show the day after a reload and after other people's runs. It
    changes nothing. It lists:
      - assigned: Assigned and Ongoing jobs the planner placed (those it gave an
        arrival time and an explanation; a job assigned by hand has neither yet);
      - unassigned: jobs the planner looked at and could not place, with the reasons;
      - skipped: jobs with no usable location (worked out live, as in a run).
    Unassigned jobs the planner has not seen yet are not listed: they wait for a run.
    """
    plan_date = plan_date or local_date(
        (clock or SystemClock()).now(), organization.timezone
    )
    jobs = (
        Job.objects.for_organization(organization)
        .filter(scheduled_date=plan_date)
        .filter(
            Q(
                status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING],
                technician__isnull=False,
            )
            | Q(status=JobStatus.UNASSIGNED)
        )
        .order_by("technician_id", "sequence_position", "id")
    )
    assigned: list[PlannedJob] = []
    unassigned: list[UnplannedJob] = []
    skipped: list[SkippedJob] = []
    for job in jobs:
        stored = job.plan_explanation or {}
        if job.status == JobStatus.UNASSIGNED:
            if not _is_located(job):
                skipped.append(_skipped(job))
            elif stored:
                unassigned.append(
                    UnplannedJob(
                        job.pk, stored.get("reasons", []), stored.get("sentence", "")
                    )
                )
        elif stored and job.estimated_arrival is not None:
            assigned.append(
                PlannedJob(
                    job.pk,
                    job.technician_id,
                    job.estimated_arrival,
                    # Explanations saved before the SLA was stored with them have no label.
                    stored.get("sla_label", "unknown"),
                    stored.get("slack_minutes", 0.0),
                    stored.get("reasons", []),
                    stored.get("sentence", ""),
                )
            )
    return ScheduleResult(plan_date, assigned, unassigned, skipped)


def _is_located(job: Job) -> bool:
    return (
        job.geocode_status in USABLE_LOCATION
        and job.lat is not None
        and job.lng is not None
    )


def _next_positions(organization, plan_date: date) -> defaultdict[int, int]:
    """For each technician, the next free stop number on `plan_date` (1 if none)."""
    rows = (
        Job.objects.for_organization(organization)
        .filter(
            status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING],
            scheduled_date=plan_date,
            technician__isnull=False,
        )
        .values("technician_id")
        .annotate(last=Max("sequence_position"))
    )
    positions: defaultdict[int, int] = defaultdict(lambda: 1)
    for row in rows:
        positions[row["technician_id"]] = (row["last"] or 0) + 1
    return positions
