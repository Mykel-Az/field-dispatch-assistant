"""SCORE stage: for a job, rank the technicians the filter let through.

Pure and deterministic (invariant 14): the same inputs give the same ranking,
whatever order the candidates arrive in, and ties are broken by technician id.
Standard library only.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Protocol

from .types import Candidate, JobView, OrgConfig, Scored, SlaLabel, TechView

# Risk falls from 1 (no slack) to 0 at this many times the "at risk" threshold.
# TIME: an estimate, tunable; the benchmark week is the place to tune it.
RISK_HORIZON_FACTOR = 4.0

# Balanced strategy weights, in minutes of travel they are worth. TIME: estimates,
# tunable. Every job a technician already has costs like 15 minutes of driving;
# going over the daily job target is a soft preference, not a hard cap, so it only
# adds cost (S2-4's "soft max jobs"); a risky arrival costs up to an hour.
WORKLOAD_MINUTES_PER_JOB = 15.0
OVER_TARGET_MINUTES = 60.0
RISK_MINUTES = 60.0


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


class NearestStrategy:
    """The closest technician wins, whatever their load."""

    def cost(
        self,
        *,
        travel_minutes: float,
        assigned_count: int,
        risk: float,
        config: OrgConfig,
    ) -> float:
        return travel_minutes


class BalancedStrategy:
    """Distance, but also how busy the technician is and how tight the arrival is."""

    def cost(
        self,
        *,
        travel_minutes: float,
        assigned_count: int,
        risk: float,
        config: OrgConfig,
    ) -> float:
        over_target = assigned_count >= config.max_jobs_per_tech_per_day
        return (
            travel_minutes
            + WORKLOAD_MINUTES_PER_JOB * assigned_count
            + (OVER_TARGET_MINUTES if over_target else 0.0)
            + RISK_MINUTES * risk
        )


# Keyed by Organization.scoring_strategy. Keep in step with that field's choices
# (a test in api/tests guards this).
STRATEGIES: Mapping[str, ScoringStrategy] = MappingProxyType(
    {"nearest": NearestStrategy(), "balanced": BalancedStrategy()}
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
