"""Run the dispatch engine for one day and save the result (ADR-008).

The engine is pure: it reads views and returns a Plan. This module is the only
place that connects it to the database. It builds the views (`adapters`), runs
ASSIGN once, and then applies each assignment through `transition`, so the job
lifecycle, the history rows and the one-ongoing-job rule all still apply.
Everything happens in one transaction: a failure leaves no half-planned day.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.db.models import F, Max, Q
from django.utils import timezone

from dispatch_engine import lifecycle as lc
from dispatch_engine.assignment import assign_jobs
from dispatch_engine.bumping import BumpCandidate, pick_bump, urgent_fit
from dispatch_engine.clock import Clock, FixedClock, SystemClock
from dispatch_engine.distance import HaversineProvider
from dispatch_engine.explanations import (
    assignment_sentence,
    explain_forced,
    forced_sentence,
    unassigned_sentence,
)
from dispatch_engine.metrics import PlanMetrics, compare
from dispatch_engine.sequencing import sequence_plan
from dispatch_engine.types import Explanation

from ..adapters import (
    _PRIORITY,
    at_local,
    job_to_view,
    org_to_config,
    technician_to_view,
)
from ..exceptions import Conflict
from ..models import GeocodeStatus, Job, JobStatus, Organization, Technician
from . import jobs as job_service
from .jobs import local_date, transition

log = logging.getLogger(__name__)

USABLE_LOCATION = (GeocodeStatus.OK, GeocodeStatus.APPROXIMATE, GeocodeStatus.MANUAL)


@dataclass(frozen=True)
class PlannedJob:
    job_id: int
    technician_id: int
    # None for a job a dispatcher assigned by hand: nobody has worked out when the
    # technician will get there.
    estimated_arrival: datetime | None
    sla_label: str
    slack_minutes: float
    reasons: list[dict]
    sentence: str
    placed_by: str = "planner"  # "planner" or "manual"


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
    replan: bool = False,
) -> ScheduleResult:
    """Assign the organization's unassigned jobs for `plan_date` (default: today there).

    Safe to run twice: only unassigned jobs are touched, and jobs that are already
    assigned stay put (invariant 12); they count as the technician's load and as
    time the technician is busy (`adapters.technician_to_view`).

    With `replan=True` the jobs the planner itself placed, and that have not started,
    are first returned to the queue and planned again, so a changed setting (the
    strategy, the daily limit) can take effect. Jobs a person assigned by hand and
    jobs under way stay (ADR-026).
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
        if replan:
            _release_planner_placements(organization, plan_date, actor)
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
        # SEQUENCE: order each technician's new jobs for driving, around what they
        # already have (ADR-028). Same views as ASSIGN got, so commitments are the same.
        plan = sequence_plan(
            plan,
            job_views.values(),
            tech_views.values(),
            config,
            distance,
            FixedClock(now),
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
                source="planner",
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

        _renumber_stops(
            organization, plan_date, {a.technician_id for a in plan.assignments}, now
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

    late = [p for p in assigned if p.slack_minutes < 0]
    log.info(
        "planner run: org %s, day %s, %d candidate jobs, %d assigned, %d unassigned, "
        "%d skipped (no location), %d expected to miss their window",
        organization.pk,
        plan_date,
        len(plannable),
        len(assigned),
        len(unassigned),
        len(skipped),
        len(late),
    )
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
      - assigned: every Assigned and Ongoing job on a technician's day. Ones the
        planner placed carry its arrival time and explanation; ones assigned by hand
        have neither and say `placed_by="manual"`;
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
        else:
            # Assigned by hand (no explanation, no arrival time): still on the
            # technician's day, so the page must show it (ADR-026).
            assigned.append(
                PlannedJob(
                    job.pk,
                    job.technician_id,
                    job.estimated_arrival,
                    "unknown",
                    0.0,
                    [],
                    "",
                    placed_by="manual",
                )
            )
    return ScheduleResult(plan_date, assigned, unassigned, skipped)


def _release_planner_placements(organization, plan_date: date, actor) -> None:
    """Return the planner's own not-yet-started placements for the day to the queue."""
    placed = (
        Job.objects.for_organization(organization)
        .select_for_update()
        .filter(
            status=JobStatus.ASSIGNED,
            scheduled_date=plan_date,
            technician__isnull=False,
        )
        .order_by("id")
    )
    for job in placed:
        last = job.history.filter(to_status=JobStatus.ASSIGNED).order_by("-id").first()
        if last is not None and last.source == "planner":
            transition(
                job,
                lc.UNASSIGNED,
                actor,
                reason="Planned again",
                source="planner",
            )


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


_STOP_SHIFT = 1000  # moves numbers out of the way while a day is renumbered


def _renumber_stops(
    organization, plan_date: date, technician_ids, now: datetime
) -> None:
    """Number each technician's whole day 1, 2, 3... in the order it runs (ADR-028).

    A new job can land in a gap before a job the technician already had, so "append
    after the last number" would give a route line that doubles back. Only the stop
    numbers of those jobs change: never the technician, the time or the status
    (invariant 12). The stop number is unique per technician and day, so every row
    is first moved out of the way and then given its final number.
    """
    for tech_id in sorted(technician_ids):
        day = Job.objects.for_organization(organization).filter(
            status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING],
            scheduled_date=plan_date,
            technician_id=tech_id,
        )
        jobs = sorted(
            day,
            key=lambda j: (
                j.status != JobStatus.ONGOING,
                j.estimated_arrival or j.slot_start or now,
                j.pk,
            ),
        )
        day.update(sequence_position=F("sequence_position") + _STOP_SHIFT)
        for number, job in enumerate(jobs, start=1):
            Job.objects.filter(pk=job.pk).update(sequence_position=number)


# ---- force-assign an urgent job (ADR-029) ------------------------------------------
class JobNotUrgent(Exception):
    """Force-assign is only for urgent jobs; a normal job is assigned the usual way."""


@dataclass(frozen=True)
class ForceAssignResult:
    job: Job
    bumped_job_ids: list[int]  # sent back to the queue (in a dry run: would be)
    estimated_arrival: datetime
    sla_label: str
    slack_minutes: float
    dry_run: bool


def _bump_slack(job: Job) -> float:
    """Minutes the job could still wait and meet its own window (0 if it has none)."""
    if job.slot_end is None:
        return 0.0
    planned = job.estimated_arrival or job.slot_start or job.slot_end
    return (job.slot_end - planned).total_seconds() / 60


def force_assign(
    *,
    job: Job,
    technician: Technician,
    actor,
    client_version: int,
    dry_run: bool = False,
    clock: Clock | None = None,
) -> ForceAssignResult:
    """Give an urgent job to `technician`, bumping jobs they have not started if needed.

    If the technician would reach the job after its deadline, the jobs that help most
    are sent back to the queue one at a time (lowest priority, then most slack), until
    the urgent job fits or no bump would help. Started jobs are never touched, and
    neither is another urgent job. Not finding a way to make the deadline is an expected
    outcome, not an error: the job is still assigned and shown as late. With
    `dry_run` nothing is written, so the dialog can show what would happen.
    """
    organization = job.organization
    config = org_to_config(organization)
    now = (clock or SystemClock()).now()
    distance = HaversineProvider(speed_mph=config.speed_mph)

    with transaction.atomic():
        # Same lock as a planner run: they take turns, so neither sees a stale day.
        Organization.objects.select_for_update().get(pk=organization.pk)
        locked = (
            Job.objects.select_for_update()
            .prefetch_related("acceptable_skills")
            .get(pk=job.pk)
        )
        if client_version != locked.version:
            raise Conflict(
                "This job was changed by someone else. Reload it.",
                code="stale_version",
            )
        if not locked.is_urgent:
            raise JobNotUrgent()
        if locked.status != JobStatus.UNASSIGNED:
            raise job_service.IllegalJobTransition(
                f"a {locked.status} job cannot be assigned"
            )
        if not _is_located(locked):
            raise job_service.LocationRequired("the job has no usable location yet")

        plan_date = locked.scheduled_date
        day_opens = at_local(plan_date, organization.work_start, organization.timezone)
        view = job_to_view(locked, urgent_clock_start=day_opens)
        workload = list(
            Job.objects.for_organization(organization)
            .select_for_update()
            .filter(
                technician=technician,
                status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING],
                scheduled_date=plan_date,
            )
            .order_by("id")
        )
        movable = {
            j.pk: j
            for j in workload
            if j.status == JobStatus.ASSIGNED and not j.is_urgent
        }

        def tech_view(held: list[Job]):
            return technician_to_view(
                technician,
                plan_date=plan_date,
                organization=organization,
                workload=held,
                now=now,
            )

        bumped: list[int] = []
        held = workload
        current = tech_view(held)
        fit = urgent_fit(view, current, config, distance, now)
        while not fit.meets_deadline:
            # Only a bump that actually brings the technician sooner is worth making.
            helpful = []
            for pk, candidate in movable.items():
                if pk in bumped:
                    continue
                without = [j for j in held if j.pk != pk]
                trial = urgent_fit(view, tech_view(without), config, distance, now)
                if trial.arrival < fit.arrival:
                    helpful.append(
                        BumpCandidate(
                            pk, _PRIORITY[candidate.priority], _bump_slack(candidate)
                        )
                    )
            pick = pick_bump(helpful)
            if pick is None:
                break  # nothing more can be done: assign anyway and show it as late
            bumped.append(pick)
            held = [j for j in held if j.pk != pick]
            current = tech_view(held)
            fit = urgent_fit(view, current, config, distance, now)

        if dry_run:
            return ForceAssignResult(
                locked, bumped, fit.arrival, str(fit.label), fit.slack_minutes, True
            )

        for pk in bumped:
            job_service.transition(
                Job.objects.get(pk=pk),
                lc.UNASSIGNED,
                actor,
                reason=f"Bumped by urgent job #{locked.pk}",
            )
        assigned = job_service.transition(
            locked,
            lc.ASSIGNED,
            actor,
            reason=f"Forced assignment ({len(bumped)} job(s) bumped)",
            technician=technician,
            client_version=client_version,
        )
        explanation = explain_forced(
            view,
            current,
            travel_minutes=fit.travel_minutes,
            slack_minutes=fit.slack_minutes,
            label=fit.label,
            bumped_count=len(bumped),
        )
        assigned.estimated_arrival = fit.arrival
        assigned.plan_explanation = {
            "reasons": reasons_as_data(explanation),
            "sentence": forced_sentence(explanation, locked.title, current.label),
            "sla_label": str(fit.label),
            "slack_minutes": fit.slack_minutes,
        }
        assigned.save(
            update_fields=["estimated_arrival", "plan_explanation", "updated_at"]
        )
        _renumber_stops(organization, plan_date, {technician.pk}, now)

    log.info(
        "force-assign: org %s, job %s to technician %s, %d bumped, slack %.0f min",
        organization.pk,
        locked.pk,
        technician.pk,
        len(bumped),
        fit.slack_minutes,
    )
    return ForceAssignResult(
        Job.objects.get(pk=locked.pk),
        bumped,
        fit.arrival,
        str(fit.label),
        fit.slack_minutes,
        False,
    )


# ---- before and after (ADR-030) ----------------------------------------------------
@dataclass(frozen=True)
class DayMetrics:
    plan_date: date
    jobs: int
    in_queue: int  # the day's jobs nobody has taken (not in either comparison)
    plan: PlanMetrics
    baseline: PlanMetrics


def day_metrics(
    *, organization, plan_date: date | None = None, clock: Clock | None = None
):
    """The plan for a day measured against a round-robin baseline on the same jobs.

    Reads only; saves nothing. The jobs are the ones with a technician (so the plan
    and the baseline do identical work); the plan is who actually has each job and in
    which stop order. Both are timed from the start of the day with no other jobs.
    """
    config = org_to_config(organization)
    now = (clock or SystemClock()).now()
    plan_date = plan_date or local_date(now, organization.timezone)
    distance = HaversineProvider(speed_mph=config.speed_mph)
    day_opens = at_local(plan_date, organization.work_start, organization.timezone)

    day = Job.objects.for_organization(organization).filter(scheduled_date=plan_date)
    placed = list(
        day.filter(
            status__in=[JobStatus.ASSIGNED, JobStatus.ONGOING, JobStatus.COMPLETED],
            technician__isnull=False,
        )
        .prefetch_related("acceptable_skills")
        .order_by("sequence_position", "id")
    )
    in_queue = day.filter(status=JobStatus.UNASSIGNED).count()

    technicians = list(
        Technician.objects.for_organization(organization)
        .select_related("user")
        .prefetch_related("skills")
        .filter(user__is_active=True)
        .order_by("id")
    )
    tech_views = [
        technician_to_view(
            t,
            plan_date=plan_date,
            organization=organization,
            workload=[],
            now=day_opens,
        )
        for t in technicians
    ]
    views = {j.pk: job_to_view(j, urgent_clock_start=day_opens) for j in placed}
    routes: dict[int, list] = defaultdict(list)
    for j in placed:
        routes[j.technician_id].append(views[j.pk])

    plan, baseline = compare(
        routes, views.values(), tech_views, config, distance, day_opens, plan_unplaced=0
    )
    return DayMetrics(plan_date, len(placed), in_queue, plan, baseline)
