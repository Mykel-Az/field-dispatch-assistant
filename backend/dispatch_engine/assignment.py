"""ASSIGN stage: give every job to the best feasible technician, or say why nobody can.

Greedy (ADR-002), in two passes (ADR-023). Pass 1 handles jobs urgent first, then
priority (high before low), then earliest deadline, then id: when capacity is short,
the jobs that matter most get the places. Pass 2 plans only the jobs pass 1 placed,
earliest deadline first, so a job with a tight window is not pushed late by a
higher-priority job whose window is wide. Pass 2 is used when it places every one of
them and leaves no more lateness than pass 1. After each assignment the technician's
free time, position and load are updated, so later jobs in the same pass see them.
The result does not depend on the order the jobs or technicians are passed in
(invariant 14). Standard library only; the decision trail is logged at DEBUG, with
ids and numbers only (ADR-019).

Daily limit (ADR-022): a normal job never goes to a technician who already has the
limit. An urgent job may, but only when the technicians under the limit would be
later (a worse SLA label) than a technician at the limit.
"""

import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from .clock import Clock
from .distance import DistanceProvider
from .explanations import explain_assignment, explain_unassigned
from .filtering import filter_technicians
from .scoring import score_candidates
from .types import (
    Assignment,
    JobView,
    OrgConfig,
    Plan,
    Scored,
    SlaLabel,
    TechView,
    Unassigned,
)

log = logging.getLogger("dispatch_engine.assign")

_LABEL_RANK = {SlaLabel.OK: 0, SlaLabel.AT_RISK: 1, SlaLabel.BREACH: 2}


def _deadline(job: JobView, config: OrgConfig) -> datetime:
    # An urgent job has no window; its deadline is creation time plus the urgent buffer.
    if job.slot_end is not None:
        return job.slot_end
    return job.created_at + timedelta(minutes=config.urgent_buffer_minutes)


def _priority_key(job: JobView, config: OrgConfig) -> tuple[bool, int, datetime, int]:
    """Pass 1: who gets the places when there are not enough."""
    return (not job.is_urgent, -job.priority, _deadline(job, config), job.id)


def _deadline_key(job: JobView, config: OrgConfig) -> tuple[bool, datetime, int, int]:
    """Pass 2: the order a technician's day should run in."""
    return (not job.is_urgent, _deadline(job, config), -job.priority, job.id)


def _late_minutes(plan: Plan) -> float:
    """Total minutes by which the plan misses windows (0 when nothing is late)."""
    return sum(max(0.0, -a.slack_minutes) for a in plan.assignments)


def _require_unique(kind: str, ids: list[int]) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {kind} ids in the input")


def _choose(
    job: JobView, ranked: tuple[Scored, ...], current: dict[int, TechView], limit: int
) -> tuple[Scored, int]:
    """The candidate to give the job to, and how many candidates were under the limit.

    A normal job only ever sees technicians under the limit (FILTER removed the
    rest), so the best-ranked one wins. An urgent job prefers the best technician
    under the limit and goes to one at the limit only when that is clearly better
    for the deadline: none are under the limit, or the best of them would be later
    (a worse label) than a technician at the limit.
    """
    under = [s for s in ranked if current[s.technician_id].assigned_count < limit]
    if not job.is_urgent:
        return ranked[0], len(under)
    if not under:
        return ranked[0], 0
    best = under[0]
    at_limit = [
        s
        for s in ranked
        if current[s.technician_id].assigned_count >= limit
        and _LABEL_RANK[s.sla_label] < _LABEL_RANK[best.sla_label]
    ]
    if at_limit:
        return min(at_limit, key=lambda s: _LABEL_RANK[s.sla_label]), len(under)
    return best, len(under)


def _pass(
    ordered: list[JobView],
    techs: list[TechView],
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
    name: str,
) -> Plan:
    """One greedy pass over `ordered`, each job to the best feasible technician."""
    current = {t.id: t for t in techs}
    assignments: list[Assignment] = []
    unassigned: list[Unassigned] = []
    debug = log.isEnabledFor(logging.DEBUG)
    if debug:
        log.debug(
            "%s: order %s",
            name,
            [
                (
                    j.id,
                    "urgent" if j.is_urgent else int(j.priority),
                    _deadline(j, config).isoformat(),
                )
                for j in ordered
            ],
        )

    for job in ordered:
        filtered = filter_technicians(
            job,
            current.values(),
            distance,
            now,
            daily_limit=config.max_jobs_per_tech_per_day,
        )
        if debug:
            log.debug(
                "%s: job %s needs skills %s, feasible %s, rejected %s",
                name,
                job.id,
                sorted(job.acceptable_skill_ids),
                [
                    (c.technician_id, c.estimated_arrival.isoformat())
                    for c in filtered.feasible
                ],
                [(r.technician_id, str(r.reason.code)) for r in filtered.rejected],
            )
        if not filtered.feasible:
            unassigned.append(
                Unassigned(
                    job.id, explain_unassigned(job, filtered.rejected, len(current))
                )
            )
            if debug:
                log.debug("%s: job %s left unassigned (nobody feasible)", name, job.id)
            continue

        ranked = score_candidates(job, filtered.feasible, current.values(), config)
        best, under_limit = _choose(
            job, ranked, current, config.max_jobs_per_tech_per_day
        )
        tech = current[best.technician_id]
        if debug:
            log.debug(
                "%s: job %s ranked %s -> technician %s (%d under the limit)",
                name,
                job.id,
                [
                    (
                        s.technician_id,
                        round(s.cost, 1),
                        round(s.slack_minutes),
                        str(s.sla_label),
                    )
                    for s in ranked
                ],
                tech.id,
                under_limit,
            )
        assignments.append(
            Assignment(
                job_id=job.id,
                technician_id=tech.id,
                estimated_arrival=best.estimated_arrival,
                slack_minutes=best.slack_minutes,
                sla_label=best.sla_label,
                risk=best.risk,
                explanation=explain_assignment(
                    job, best, tech, config, len(ranked), under_limit, filtered.rejected
                ),
            )
        )
        # The technician is now busy until the job ends, and ends up where it is.
        current[tech.id] = replace(
            tech,
            free_at=best.estimated_arrival + timedelta(minutes=job.duration_minutes),
            position=job.location,
            assigned_count=tech.assigned_count + 1,
        )

    return Plan(tuple(assignments), tuple(unassigned))


def assign_jobs(
    jobs: Iterable[JobView],
    technicians: Iterable[TechView],
    config: OrgConfig,
    distance: DistanceProvider,
    clock: Clock,
) -> Plan:
    jobs = list(jobs)
    techs = list(technicians)
    _require_unique("job", [j.id for j in jobs])
    _require_unique("technician", [t.id for t in techs])

    now = clock.now()  # read once: one run, one instant
    log.debug(
        "assign: %d jobs, %d technicians, now %s, strategy %s, limit %d",
        len(jobs),
        len(techs),
        now.isoformat(),
        config.scoring_strategy,
        config.max_jobs_per_tech_per_day,
    )

    first = _pass(
        sorted(jobs, key=lambda j: _priority_key(j, config)),
        techs,
        config,
        distance,
        now,
        "pass 1 (priority)",
    )
    placed = {a.job_id for a in first.assignments}
    if len(placed) < 2:
        return first

    second = _pass(
        sorted(
            (j for j in jobs if j.id in placed), key=lambda j: _deadline_key(j, config)
        ),
        techs,
        config,
        distance,
        now,
        "pass 2 (deadline)",
    )
    late_first, late_second = _late_minutes(first), _late_minutes(second)
    use_second = len(second.assignments) == len(placed) and late_second <= late_first
    log.debug(
        "assign: pass 2 %s (placed %d of %d, late %.0f min vs %.0f min in pass 1)",
        "used" if use_second else "not used",
        len(second.assignments),
        len(placed),
        late_second,
        late_first,
    )
    if not use_second:
        return first
    # Who was left out, and why, was decided in pass 1, in priority order.
    return Plan(second.assignments, first.unassigned)
