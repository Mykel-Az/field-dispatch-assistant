"""Force-assign an urgent job: who gets bumped when the technician cannot make the deadline.

A dispatcher gives an urgent job to a chosen technician (ADR-029). If that technician
would reach it after its deadline, jobs they have not started are sent back to the
queue, one at a time, until the urgent job fits or nothing is left to bump. Pure and
deterministic (invariant 14). Standard library only; ids and numbers, no customer
data (ADR-019).

The bump rule: only jobs that are not urgent and not started can be bumped (the service
passes only those), and the one to go first is the lowest priority, then the one with
the most slack (it can best afford to wait for the next plan), then the lowest id.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from .distance import DistanceProvider
from .filtering import _arrival
from .scoring import deadline_for, sla_label
from .types import JobView, OrgConfig, Priority, SlaLabel, TechView


@dataclass(frozen=True, slots=True)
class BumpCandidate:
    """A job the technician has but has not started, and could give up."""

    job_id: int
    priority: Priority
    slack_minutes: float  # how long it could still wait and meet its own deadline


def pick_bump(candidates: Iterable[BumpCandidate]) -> int | None:
    """The job to send back first, or None when there is nothing to bump."""
    ordered = sorted(candidates, key=lambda c: (c.priority, -c.slack_minutes, c.job_id))
    return ordered[0].job_id if ordered else None


@dataclass(frozen=True, slots=True)
class UrgentFit:
    arrival: datetime
    travel_minutes: float
    slack_minutes: float
    label: SlaLabel

    @property
    def meets_deadline(self) -> bool:
        return self.slack_minutes >= 0


def urgent_fit(
    job: JobView,
    tech: TechView,
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
) -> UrgentFit:
    """When this technician would reach the urgent job, given what they hold now."""
    arrival, travel = _arrival(job, tech, distance, now)
    deadline = deadline_for(job, travel, config)
    slack = (deadline - arrival).total_seconds() / 60
    return UrgentFit(arrival, travel, slack, sla_label(slack, config.at_risk_minutes))
