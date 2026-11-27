"""Before and after: what the planner buys compared with a naive dispatcher (ADR-030).

The same jobs and the same technicians are measured two ways:
  - the plan as it stands (who does what, in which order), and
  - a baseline that deals the jobs out round-robin among technicians who have a skill
    for them, in the order the requests came in, with no look at distance, load,
    deadlines or priority. This is how a dispatcher without a planner works.

Both are timed by the same simulation (the engine's own arrival rules, from the start of
the day, no existing jobs), so the difference is the decisions, not the arithmetic.
Pure and deterministic (invariant 14); ids and numbers only (ADR-019).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from .distance import DistanceProvider
from .sequencing import _simulate
from .types import JobView, OrgConfig, TechView


@dataclass(frozen=True, slots=True)
class PlanMetrics:
    jobs: int  # jobs placed with a technician
    unplaced: int  # jobs nobody could take
    sla_breaches: int  # jobs that arrive after their deadline
    late_minutes: int  # total minutes late over those jobs
    travel_miles: float  # driving from the workstation through every stop
    min_jobs: int  # fewest jobs any technician has
    max_jobs: int  # most jobs any technician has

    @property
    def workload_spread(self) -> int:
        return self.max_jobs - self.min_jobs


def round_robin(
    jobs: Iterable[JobView], technicians: Iterable[TechView]
) -> tuple[dict[int, list[JobView]], list[JobView]]:
    """Deal jobs out in request order (by id), skipping technicians without the skill.

    Returns each technician's jobs in the order dealt, and the jobs nobody could take.
    """
    techs = sorted(technicians, key=lambda t: t.id)
    routes: dict[int, list[JobView]] = {t.id: [] for t in techs}
    unplaced: list[JobView] = []
    pointer = 0
    for job in sorted(jobs, key=lambda j: j.id):
        for step in range(len(techs)):
            tech = techs[(pointer + step) % len(techs)]
            if tech.skill_ids & job.acceptable_skill_ids:
                routes[tech.id].append(job)
                pointer = (pointer + step + 1) % len(techs)
                break
        else:
            unplaced.append(job)
    return routes, unplaced


def measure(
    routes: Mapping[int, Sequence[JobView]],
    technicians: Iterable[TechView],
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
    *,
    unplaced: int = 0,
) -> PlanMetrics:
    """Time each technician's route in the order given and add up the three measures."""
    techs = {t.id: t for t in technicians}
    breaches = late = 0
    miles = 0.0
    counts: list[int] = []
    for tech_id in sorted(techs):
        tech = techs[tech_id]
        order = list(routes.get(tech_id, ()))
        counts.append(len(order))
        route = _simulate(order, tech, config, distance, now)
        here = tech.position
        for stop in route.stops:
            miles += distance.miles(here, stop.job.location)
            here = stop.job.location
            if stop.slack_minutes < 0:
                breaches += 1
                late += round(-stop.slack_minutes)
    return PlanMetrics(
        jobs=sum(counts),
        unplaced=unplaced,
        sla_breaches=breaches,
        late_minutes=late,
        travel_miles=round(miles, 1),
        min_jobs=min(counts, default=0),
        max_jobs=max(counts, default=0),
    )


def compare(
    plan_routes: Mapping[int, Sequence[JobView]],
    jobs: Iterable[JobView],
    technicians: Iterable[TechView],
    config: OrgConfig,
    distance: DistanceProvider,
    now: datetime,
    *,
    plan_unplaced: int = 0,
) -> tuple[PlanMetrics, PlanMetrics]:
    """(the plan, the round-robin baseline) for the same jobs and technicians."""
    techs = list(technicians)
    jobs = list(jobs)
    deal, left_over = round_robin(jobs, techs)
    plan = measure(plan_routes, techs, config, distance, now, unplaced=plan_unplaced)
    baseline = measure(deal, techs, config, distance, now, unplaced=len(left_over))
    return plan, baseline
