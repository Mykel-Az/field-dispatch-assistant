"""ASSIGN stage: give every job to the best feasible technician, or say why nobody can.

Greedy, one pass (ADR-002). Jobs are handled in this order: urgent first, then
priority (high before low), then earliest deadline, then id. Earliest deadline keeps
each technician's day moving forward in time, so a 9 am job is not planned after a
3 pm one. After each assignment the technician's free time, position and load are
updated, so later jobs in the same run see them. The result does not depend on the
order the jobs or technicians are passed in (invariant 14). Standard library only.

Daily limit (ADR-022): a normal job never goes to a technician who already has the
limit. An urgent job may, but only when the technicians under the limit would be
later (a worse SLA label) than a technician at the limit.
"""

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

_LABEL_RANK = {SlaLabel.OK: 0, SlaLabel.AT_RISK: 1, SlaLabel.BREACH: 2}


def _order_key(job: JobView, config: OrgConfig) -> tuple[bool, int, datetime, int]:
    # An urgent job has no window; its deadline is creation time plus the urgent buffer.
    deadline = (
        job.slot_end
        if job.slot_end is not None
        else job.created_at + timedelta(minutes=config.urgent_buffer_minutes)
    )
    return (not job.is_urgent, -job.priority, deadline, job.id)


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
    current = {t.id: t for t in techs}
    assignments: list[Assignment] = []
    unassigned: list[Unassigned] = []

    for job in sorted(jobs, key=lambda j: _order_key(j, config)):
        filtered = filter_technicians(
            job,
            current.values(),
            distance,
            now,
            daily_limit=config.max_jobs_per_tech_per_day,
        )
        if not filtered.feasible:
            unassigned.append(
                Unassigned(
                    job.id, explain_unassigned(job, filtered.rejected, len(current))
                )
            )
            continue

        ranked = score_candidates(job, filtered.feasible, current.values(), config)
        best, under_limit = _choose(
            job, ranked, current, config.max_jobs_per_tech_per_day
        )
        tech = current[best.technician_id]
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
