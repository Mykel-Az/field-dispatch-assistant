"""FILTER stage: which technicians can take this job, and why the others cannot.

Pure and deterministic (invariant 14): technicians are visited in id order, and
the result does not depend on the order they were passed in. This stage only
rejects. It does not rank or choose; SCORE and ASSIGN do that.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta

from .distance import DistanceProvider
from .types import (
    Candidate,
    FilterResult,
    JobView,
    Reason,
    ReasonCode,
    Rejection,
    TechView,
)


def _arrival(
    job: JobView, tech: TechView, travel_minutes: float, now: datetime
) -> datetime:
    """When this technician would reach the job.

    They cannot leave before now, before they are free, or before their shift
    starts. For a job with a slot, the estimated arrival is never earlier than the
    slot opening: the customer is only expected from then. A job without a slot is
    planned as early as the technician can reach it.
    """
    start = max(now, tech.free_at, tech.shift_start)
    arrival = start + timedelta(minutes=travel_minutes)
    if job.slot_start is not None:
        arrival = max(arrival, job.slot_start)
    return arrival


def _reject(tech: TechView, code: ReasonCode, **facts: float | str) -> Rejection:
    return Rejection(tech.id, Reason(code, {"technician_id": tech.id, **facts}))


def filter_technicians(
    job: JobView,
    technicians: Iterable[TechView],
    distance: DistanceProvider,
    now: datetime,
) -> FilterResult:
    """Split technicians into those who can take the job and those who cannot.

    Rules, checked in this order (the first failure is the one reason given):
      1. available;
      2. at least one skill in common with the job (any-of, invariant 2);
      3. arrival no later than the end of their shift (ADR-012).
    """
    feasible: list[Candidate] = []
    rejected: list[Rejection] = []

    for tech in sorted(technicians, key=lambda t: t.id):
        if not tech.is_available:
            rejected.append(_reject(tech, ReasonCode.UNAVAILABLE))
            continue

        if not tech.skill_ids & job.acceptable_skill_ids:
            rejected.append(_reject(tech, ReasonCode.SKILL_MISMATCH, job_id=job.id))
            continue

        travel = distance.travel_minutes(tech.position, job.location)
        arrival = _arrival(job, tech, travel, now)
        if arrival > tech.shift_end:  # arriving exactly at closing is still allowed
            late = (arrival - tech.shift_end).total_seconds() / 60
            rejected.append(
                _reject(
                    tech, ReasonCode.AFTER_CLOSING, minutes_after_closing=round(late, 1)
                )
            )
            continue

        feasible.append(Candidate(tech.id, arrival, travel))

    return FilterResult(tuple(feasible), tuple(rejected))
