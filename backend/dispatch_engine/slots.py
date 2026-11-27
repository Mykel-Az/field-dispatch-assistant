"""Which times could a new job be booked? (ADR-032)

Answers a customer on the phone: "when could someone come?" It asks the same FILTER
rules the planner uses (skills, availability, daily limit, arrival before closing) and
the same gap-fitting arrival (ADR-027), for a job that has no window yet. It reads
only; it books nothing.

Standard library only; no customer data (ADR-019).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .distance import DistanceProvider
from .filtering import filter_technicians
from .types import JobView, TechView


@dataclass(frozen=True, slots=True)
class Slot:
    technician_id: int
    start: datetime
    end: datetime
    travel_minutes: float


def earliest_slots(
    job: JobView,
    technicians: Iterable[TechView],
    distance: DistanceProvider,
    now: datetime,
    daily_limit: int | None = None,
) -> list[Slot]:
    """The earliest start for each technician who could take `job`, soonest first.

    `job` carries no window: the customer has not agreed to a time yet. Ties go to the
    lower technician id (invariant 14).
    """
    feasible = filter_technicians(job, technicians, distance, now, daily_limit).feasible
    length = timedelta(minutes=job.duration_minutes)
    slots = [
        Slot(
            c.technician_id,
            c.estimated_arrival,
            c.estimated_arrival + length,
            c.travel_minutes,
        )
        for c in feasible
    ]
    return sorted(slots, key=lambda s: (s.start, s.technician_id))
