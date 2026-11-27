"""Re-estimate arrival times for a technician's remaining stops (ADR-031).

When a job runs over (or finishes early) the next stops arrive later (or sooner) than
the plan said. This stage restates times, slack and labels for the stops in the order
they already have. It never changes who does a job and never changes the order
(invariants 11 and 13); the dispatcher is told a stop is now late and decides.

Standard library only; no customer data (ADR-019).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from .distance import DistanceProvider
from .scoring import sla_label
from .sequencing import _simulate
from .types import JobView, Location, OrgConfig, SlaLabel, TechView


@dataclass(frozen=True, slots=True)
class Estimate:
    job_id: int
    estimated_arrival: datetime
    slack_minutes: float
    sla_label: SlaLabel


def reestimate(
    remaining: Sequence[JobView],
    tech: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    *,
    now: datetime,
    position: Location,
) -> list[Estimate]:
    """New arrival, slack and label for each remaining stop, in the order given.

    The technician is free at `now`, at `position` (where they just finished), with no
    other commitments: the remaining stops are the rest of their day. Stops are
    returned in the same order as `remaining`.
    """
    start = replace(tech, free_at=now, position=position, commitments=())
    route = _simulate(remaining, start, config, distance, now)
    return [
        Estimate(
            s.job.id,
            s.arrival,
            s.slack_minutes,
            sla_label(s.slack_minutes, config.at_risk_minutes),
        )
        for s in route.stops
    ]
