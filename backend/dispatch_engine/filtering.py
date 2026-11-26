"""FILTER stage: which technicians can take this job, and why the others cannot.

Pure and deterministic (invariant 14): technicians are visited in id order, and
the result does not depend on the order they were passed in. This stage only
rejects. It does not rank or choose; SCORE and ASSIGN do that.
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from .distance import DistanceProvider
from .types import (
    Candidate,
    Commitment,
    FilterResult,
    JobView,
    Reason,
    ReasonCode,
    Rejection,
    TechView,
)


def _arrival(
    job: JobView,
    tech: TechView,
    distance: DistanceProvider,
    now: datetime,
) -> tuple[datetime, float]:
    """When this technician would reach the job, and the drive that takes.

    They cannot leave before now or before their shift starts. For a job with a slot,
    the estimated arrival is never earlier than the slot opening: the customer is only
    expected from then. A job without a slot is planned as early as possible.

    The earliest place wins. Before each existing commitment the job fits only if the
    technician can get there, do the job, and drive on to the commitment before it
    starts (ADR-027); otherwise the search moves past that commitment. After the last
    commitment the technician is at `position`, free from `free_at`.
    """
    cursor_time = max(now, tech.shift_start)
    cursor_at = tech.home or tech.position
    duration = timedelta(minutes=job.duration_minutes)

    def reach(from_at, from_time):
        travel = distance.travel_minutes(from_at, job.location)
        arrival = from_time + timedelta(minutes=travel)
        if job.slot_start is not None:
            arrival = max(arrival, job.slot_start)
        return arrival, travel

    for commitment in tech.commitments:
        if commitment.end <= cursor_time:
            continue  # already over
        arrival, travel = reach(cursor_at, cursor_time)
        onward = distance.travel_minutes(job.location, commitment.location)
        if arrival + duration + timedelta(minutes=onward) <= commitment.start:
            return arrival, travel
        cursor_time = max(cursor_time, commitment.end)
        cursor_at = commitment.location

    # After everything already on the day. With no commitments `free_at` and `position`
    # are the whole story (a technician who is simply busy, as before).
    return reach(
        tech.position if tech.commitments else cursor_at, max(cursor_time, tech.free_at)
    )


def commit_job(tech: TechView, job: JobView, arrival: datetime) -> TechView:
    """The technician after taking `job` at `arrival`: the job is now a commitment.

    If it is the last thing on the day the technician ends up where it is; if it went
    into a gap before a later job they do not. Shared by ASSIGN and SEQUENCE so both
    describe a growing day the same way.
    """
    ends = arrival + timedelta(minutes=job.duration_minutes)
    last = ends >= tech.free_at
    return replace(
        tech,
        free_at=max(tech.free_at, ends),
        position=job.location if last else tech.position,
        assigned_count=tech.assigned_count + 1,
        commitments=tuple(
            sorted(
                (*tech.commitments, Commitment(arrival, ends, job.location)),
                key=lambda c: (c.start, c.end),
            )
        ),
        home=tech.home or tech.position,
    )


def _reject(tech: TechView, code: ReasonCode, **facts: float | str) -> Rejection:
    return Rejection(tech.id, Reason(code, {"technician_id": tech.id, **facts}))


def filter_technicians(
    job: JobView,
    technicians: Iterable[TechView],
    distance: DistanceProvider,
    now: datetime,
    daily_limit: int | None = None,
) -> FilterResult:
    """Split technicians into those who can take the job and those who cannot.

    Rules, checked in this order (the first failure is the one reason given):
      1. available;
      2. at least one skill in common with the job (any-of, invariant 2);
      3. a normal job only: the technician is under the daily job limit (ADR-022);
         an urgent job may go over it, so ASSIGN decides that case;
      4. arrival no later than the end of their shift (ADR-012).
    `daily_limit=None` means no limit.
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

        if (
            daily_limit is not None
            and not job.is_urgent
            and tech.assigned_count >= daily_limit
        ):
            rejected.append(
                _reject(
                    tech,
                    ReasonCode.DAILY_LIMIT,
                    assigned_count=tech.assigned_count,
                    limit=daily_limit,
                )
            )
            continue

        arrival, travel = _arrival(job, tech, distance, now)
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
