"""SEQUENCE stage: put each technician's newly planned jobs in driving order (ADR-003, ADR-028).

ASSIGN decides who does a job. This stage decides the order of one technician's new
stops. It never changes who does a job and never drops one (invariant 11); it only
reorders, and recomputes arrival times, slack and labels for the new order.

Jobs the technician already has (Assigned or Ongoing) are fixed commitments
(invariant 12, ADR-027): new jobs are fitted into the gaps between them, exactly as
ASSIGN does, through the same `filtering._arrival`. A reorder therefore never moves
an existing job and never puts a new job on top of one.

The rule, step by step, for one technician:
  1. Candidates are the remaining jobs that can still be reached on time
     (slot-feasible): going to one does not make the rest of the day later than
     following the deadlines would.
  2. An urgent job goes first when it is among them.
  3. Among the rest, the nearest job that needs no waiting for its window wins; if
     every candidate would have to wait, the one reached soonest wins.
  4. The first stop is therefore the job nearest where the technician starts (the
     workstation on a fresh day), unless its window does not allow going first.
Ties are broken by earlier deadline, then id (invariant 14).

Safety net: the nearest-first order replaces the order ASSIGN produced only when it
is no later in total and drives less. So sequencing can never make a day worse.

Standard library only; no customer data (ADR-019).
"""

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from .clock import Clock
from .distance import DistanceProvider
from .explanations import explain_stop
from .filtering import _arrival, commit_job
from .scoring import deadline_for, risk_score, sla_label
from .types import Assignment, JobView, OrgConfig, Plan, TechView

log = logging.getLogger("dispatch_engine.sequence")

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class _Stop:
    job: JobView
    travel_minutes: float
    arrival: datetime
    slack_minutes: float

    @property
    def waits(self) -> bool:
        """The technician is there before the customer's window opens and must wait."""
        return self.job.slot_start is not None and self.arrival <= self.job.slot_start


@dataclass(frozen=True, slots=True)
class _Route:
    stops: tuple[_Stop, ...]  # in the order they were planned

    @property
    def late_minutes(self) -> float:
        return sum(max(0.0, -s.slack_minutes) for s in self.stops)

    @property
    def travel_total(self) -> float:
        return sum(s.travel_minutes for s in self.stops)

    @property
    def in_time_order(self) -> tuple[_Stop, ...]:
        """With gaps, a job planned later can be driven earlier: the day runs by the clock."""
        return tuple(sorted(self.stops, key=lambda s: (s.arrival, s.job.id)))


def _next_stop(
    job: JobView,
    state: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
) -> _Stop:
    """Where and when this technician would be if `job` were placed next."""
    arrival, travel = _arrival(job, state, distance, now)
    deadline = deadline_for(job, travel, config)
    return _Stop(job, travel, arrival, (deadline - arrival).total_seconds() / 60)


def _simulate(
    order: Iterable[JobView],
    tech: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
) -> _Route:
    """Place the jobs one by one in this order (each becomes a commitment) and record arrivals."""
    state = tech
    stops: list[_Stop] = []
    for job in order:
        stop = _next_stop(job, state, config, distance, now)
        stops.append(stop)
        state = commit_job(state, job, stop.arrival)
    return _Route(tuple(stops))


def _deadline_order(jobs: Iterable[JobView], config: OrgConfig) -> list[JobView]:
    return sorted(
        jobs, key=lambda j: (not j.is_urgent, deadline_for(j, 0.0, config), j.id)
    )


def _nearest_first(
    jobs: list[JobView],
    tech: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
) -> _Route:
    """Greedy nearest-next order that never makes the rest of the day later than necessary."""
    order: list[JobView] = []
    remaining = sorted(jobs, key=lambda j: j.id)
    state = tech

    while remaining:
        # What the rest of the day costs if we simply follow the deadlines from here.
        reference = _simulate(
            _deadline_order(remaining, config), state, config, distance, now
        ).late_minutes

        options: list[_Stop] = []
        for job in remaining:
            stop = _next_stop(job, state, config, distance, now)
            rest = [j for j in remaining if j.id != job.id]
            tail = _simulate(
                _deadline_order(rest, config),
                commit_job(state, job, stop.arrival),
                config,
                distance,
                now,
            ).late_minutes
            # Slot-feasible: it does not push the day later than the deadline order would.
            if max(0.0, -stop.slack_minutes) + tail <= reference + _EPS:
                options.append(stop)

        if not options:  # cannot happen (the first deadline job always qualifies)
            first = _deadline_order(remaining, config)[0]
            options = [_next_stop(first, state, config, distance, now)]

        pool = [s for s in options if s.job.is_urgent] or options
        no_wait = [s for s in pool if not s.waits]
        if no_wait:
            chosen = min(
                no_wait,
                key=lambda s: (
                    s.travel_minutes,
                    deadline_for(s.job, 0.0, config),
                    s.job.id,
                ),
            )
        else:
            chosen = min(pool, key=lambda s: (s.arrival, s.travel_minutes, s.job.id))

        order.append(chosen.job)
        remaining = [j for j in remaining if j.id != chosen.job.id]
        state = commit_job(state, chosen.job, chosen.arrival)

    return _simulate(order, tech, config, distance, now)


def sequence_route(
    jobs: list[JobView],
    tech: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
) -> tuple[_Route, bool]:
    """The order for one technician's new jobs, and whether it differs from `jobs`.

    `jobs` is in the order ASSIGN planned them. The nearest-first order is used only
    when it is no later in total and drives less.
    """
    baseline = _simulate(jobs, tech, config, distance, now)
    if len(jobs) < 2:
        return baseline, False
    nearest = _nearest_first(jobs, tech, config, distance, now)
    better = nearest.late_minutes < baseline.late_minutes - _EPS or (
        nearest.late_minutes <= baseline.late_minutes + _EPS
        and nearest.travel_total < baseline.travel_total - _EPS
    )
    if not better:
        return baseline, False
    return nearest, [s.job.id for s in nearest.stops] != [j.id for j in jobs]


def sequence_plan(
    plan: Plan,
    jobs: Iterable[JobView],
    technicians: Iterable[TechView],
    config: OrgConfig,
    distance: DistanceProvider,
    clock: Clock,
) -> Plan:
    """Reorder every technician's new jobs and restate arrival, slack and reasons.

    `technicians` must be the same views that were given to ASSIGN (before it ran), so a
    technician's commitments are the jobs they already had. The result lists
    assignments technician by technician, in the order the day runs. `unassigned` is
    returned unchanged.
    """
    jobs_by_id = {j.id: j for j in jobs}
    techs_by_id = {t.id: t for t in technicians}
    now = clock.now()

    by_tech: dict[int, list[JobView]] = defaultdict(list)
    originals: dict[int, Assignment] = {}
    for a in plan.assignments:  # ASSIGN's order is the baseline
        by_tech[a.technician_id].append(jobs_by_id[a.job_id])
        originals[a.job_id] = a

    result: list[Assignment] = []
    for tech_id in sorted(by_tech):
        route, reordered = sequence_route(
            by_tech[tech_id], techs_by_id[tech_id], config, distance, now
        )
        stops = route.in_time_order
        log.debug(
            "sequence: technician %s order %s (reordered %s, late %.0f min, drive %.0f min)",
            tech_id,
            [s.job.id for s in stops],
            reordered,
            route.late_minutes,
            route.travel_total,
        )
        previous_id = 0  # 0: first of this run
        for index, stop in enumerate(stops, start=1):
            old = originals[stop.job.id]
            label = sla_label(stop.slack_minutes, config.at_risk_minutes)
            result.append(
                Assignment(
                    job_id=old.job_id,
                    technician_id=tech_id,
                    estimated_arrival=stop.arrival,
                    slack_minutes=stop.slack_minutes,
                    sla_label=label,
                    risk=risk_score(stop.slack_minutes, config.at_risk_minutes),
                    explanation=explain_stop(
                        old.explanation,
                        travel_minutes=stop.travel_minutes,
                        slack_minutes=stop.slack_minutes,
                        label=label,
                        stop=index,
                        stops=len(stops),
                        previous_job_id=previous_id,
                        reordered=reordered,
                    ),
                )
            )
            previous_id = stop.job.id
    return Plan(tuple(result), plan.unassigned)
