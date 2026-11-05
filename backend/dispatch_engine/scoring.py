"""SCORE stage: for a job, rank the technicians the filter let through.

Pure and deterministic (invariant 14): the same inputs give the same ranking,
whatever order the candidates arrive in, and ties are broken by technician id.
Standard library only.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Protocol

from .types import Candidate, JobView, OrgConfig, Scored, SlaLabel, TechView

# Risk falls from 1 (no slack) to 0 at this many times the "at risk" threshold.
# TIME: an estimate, tunable; the benchmark week is the place to tune it.
RISK_HORIZON_FACTOR = 4.0


def deadline_for(job: JobView, travel_minutes: float, config: OrgConfig) -> datetime:
    """The latest the technician may arrive (invariant 4).

    A job with a window: the end of the window. An urgent job (no window): its
    creation time plus the travel and the organization's urgent buffer.
    """
    if job.slot_end is not None:
        return job.slot_end
    return job.created_at + timedelta(
        minutes=travel_minutes + config.urgent_buffer_minutes
    )


def sla_label(slack_minutes: float, at_risk_minutes: float) -> SlaLabel:
    """Arriving exactly on the deadline is on time, so zero slack is 'at risk', not 'breach'."""
    if slack_minutes < 0:
        return SlaLabel.BREACH
    if slack_minutes < at_risk_minutes:
        return SlaLabel.AT_RISK
    return SlaLabel.OK


def risk_score(slack_minutes: float, at_risk_minutes: float) -> float:
    """0 (plenty of slack) to 1 (none or negative). Used for ranking only."""
    if slack_minutes <= 0:
        return 1.0
    horizon = RISK_HORIZON_FACTOR * at_risk_minutes
    if slack_minutes >= horizon:
        return 0.0
    return 1.0 - slack_minutes / horizon


class ScoringStrategy(Protocol):
    """How to turn one candidate's numbers into a cost. Lower is better."""

    def cost(
        self,
        *,
        travel_minutes: float,
        assigned_count: int,
        risk: float,
        config: OrgConfig,
    ) -> float: ...


@dataclass(frozen=True, slots=True)
class Weights:
    """What each factor is worth, in minutes of travel.

    Every strategy counts every factor; strategies differ only in emphasis. TIME:
    these numbers are estimates, tunable; the benchmark week is the place to tune.
    """

    travel: float  # per minute of driving
    per_job: float  # per job the technician already has
    over_target: float  # extra when at or over the daily job target (soft, not a cap)
    risk: float  # times the internal 0-1 risk of a tight arrival


# Closest technician wins, unless another is within about 10 minutes of driving and
# clearly less loaded: three extra jobs, being at the daily target, or a tight
# arrival each count for roughly 10 minutes.
NEAREST_WEIGHTS = Weights(travel=1.0, per_job=3.0, over_target=10.0, risk=10.0)
# Distance, but also how busy the technician is and how tight the arrival is.
BALANCED_WEIGHTS = Weights(travel=1.0, per_job=15.0, over_target=60.0, risk=60.0)


class WeightedStrategy:
    """cost = weighted sum of travel, load, over-target and risk."""

    def __init__(self, weights: Weights) -> None:
        self.weights = weights

    def cost(
        self,
        *,
        travel_minutes: float,
        assigned_count: int,
        risk: float,
        config: OrgConfig,
    ) -> float:
        w = self.weights
        over_target = assigned_count >= config.max_jobs_per_tech_per_day
        return (
            w.travel * travel_minutes
            + w.per_job * assigned_count
            + (w.over_target if over_target else 0.0)
            + w.risk * risk
        )


# Keyed by Organization.scoring_strategy. Keep in step with that field's choices
# (a test in api/tests guards this).
STRATEGIES: Mapping[str, ScoringStrategy] = MappingProxyType(
    {
        "nearest": WeightedStrategy(NEAREST_WEIGHTS),
        "balanced": WeightedStrategy(BALANCED_WEIGHTS),
    }
)


def get_strategy(name: str) -> ScoringStrategy:
    try:
        return STRATEGIES[name]
    except KeyError:
        valid = ", ".join(sorted(STRATEGIES))
        raise ValueError(
            f"unknown scoring strategy {name!r}; choose one of: {valid}"
        ) from None


def score_candidates(
    job: JobView,
    candidates: Iterable[Candidate],
    technicians: Iterable[TechView],
    config: OrgConfig,
) -> tuple[Scored, ...]:
    """Score every candidate and return them best first (lowest cost, then lowest id)."""
    strategy = get_strategy(config.scoring_strategy)
    by_id = {t.id: t for t in technicians}

    scored = []
    for candidate in candidates:
        deadline = deadline_for(job, candidate.travel_minutes, config)
        slack = (deadline - candidate.estimated_arrival).total_seconds() / 60
        risk = risk_score(slack, config.at_risk_minutes)
        cost = strategy.cost(
            travel_minutes=candidate.travel_minutes,
            assigned_count=by_id[candidate.technician_id].assigned_count,
            risk=risk,
            config=config,
        )
        scored.append(
            Scored(
                technician_id=candidate.technician_id,
                estimated_arrival=candidate.estimated_arrival,
                travel_minutes=candidate.travel_minutes,
                slack_minutes=slack,
                sla_label=sla_label(slack, config.at_risk_minutes),
                risk=risk,
                cost=cost,
            )
        )
    return tuple(sorted(scored, key=lambda s: (s.cost, s.technician_id)))
