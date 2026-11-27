"""Explanations: structured reasons (codes and numbers) first, plain English built from them.

The reasons are the explanation of record. The sentences below are templates over
those facts, so every number in a sentence appears in the facts. Standard library only.
"""

import math
from collections.abc import Iterable, Mapping

from .types import (
    Assignment,
    Explanation,
    JobView,
    OrgConfig,
    Reason,
    ReasonCode,
    Rejection,
    Scored,
    SlaLabel,
    TechView,
    Unassigned,
)


# ---- structured reasons -----------------------------------------------------
def explain_assignment(
    job: JobView,
    chosen: Scored,
    tech: TechView,
    config: OrgConfig,
    feasible_count: int,
    under_limit_count: int,
    rejected: Iterable[Rejection],
) -> Explanation:
    """Why this technician got this job. Minutes are whole numbers, so the text matches the facts."""
    slack = math.floor(chosen.slack_minutes)
    reasons = [
        Reason(
            ReasonCode.ASSIGNED,
            {
                "job_id": job.id,
                "technician_id": tech.id,
                "travel_minutes": round(chosen.travel_minutes),
                "slack_minutes": slack,
                "candidates": feasible_count,
                "strategy": config.scoring_strategy,
            },
        )
    ]
    if chosen.same_site:
        reasons.append(Reason(ReasonCode.SAME_SITE, {"technician_id": tech.id}))
    if chosen.sla_label == SlaLabel.AT_RISK:
        reasons.append(Reason(ReasonCode.SLA_AT_RISK, {"slack_minutes": slack}))
    elif chosen.sla_label == SlaLabel.BREACH:
        reasons.append(Reason(ReasonCode.SLA_BREACH, {"late_minutes": -slack}))
    if tech.assigned_count >= config.max_jobs_per_tech_per_day:
        # Only an urgent job can get here: FILTER keeps normal jobs under the limit.
        reasons.append(
            Reason(
                ReasonCode.URGENT_OVER_LIMIT,
                {
                    "technician_id": tech.id,
                    "assigned_count": tech.assigned_count,
                    "limit": config.max_jobs_per_tech_per_day,
                    "under_limit_candidates": under_limit_count,
                },
            )
        )
    # Keep why the others could not take it: this is what "why not technician X?" needs.
    reasons.extend(r.reason for r in rejected)
    return Explanation(tuple(reasons))


def explain_stop(
    explanation: Explanation,
    *,
    travel_minutes: float,
    slack_minutes: float,
    label: SlaLabel,
    stop: int,
    stops: int,
    previous_job_id: int,
    reordered: bool,
) -> Explanation:
    """Restate an assignment's reasons after SEQUENCE: new drive time, slack and label, plus the stop.

    ASSIGN worked out travel and slack for the moment it placed the job. Once the
    route is ordered the job is reached from a different place, so those numbers
    change. Every other reason (limits, why others were rejected) is kept as it was.
    `previous_job_id` is 0 for the first stop. Minutes are whole numbers, so the
    text matches the facts.
    """
    slack = math.floor(slack_minutes)
    kept: list[Reason] = []
    for reason in explanation.reasons:
        if reason.code in (ReasonCode.SLA_AT_RISK, ReasonCode.SLA_BREACH):
            continue  # restated below from the new slack
        if reason.code == ReasonCode.ASSIGNED:
            reason = Reason(
                reason.code,
                {
                    **reason.facts,
                    "travel_minutes": round(travel_minutes),
                    "slack_minutes": slack,
                },
            )
        kept.append(reason)
    after_assigned: list[Reason] = []
    if label == SlaLabel.AT_RISK:
        after_assigned.append(Reason(ReasonCode.SLA_AT_RISK, {"slack_minutes": slack}))
    elif label == SlaLabel.BREACH:
        after_assigned.append(Reason(ReasonCode.SLA_BREACH, {"late_minutes": -slack}))
    after_assigned.append(
        Reason(
            ReasonCode.STOP_ORDER,
            {
                "stop": stop,
                "stops": stops,
                "previous_job_id": previous_job_id,
                "drive_minutes": round(travel_minutes),
                "reordered": int(reordered),
            },
        )
    )
    return Explanation((kept[0], *after_assigned, *kept[1:]))


def explain_forced(
    job: JobView,
    tech: TechView,
    *,
    travel_minutes: float,
    slack_minutes: float,
    label: SlaLabel,
    bumped_count: int,
) -> Explanation:
    """Why an urgent job is with this technician: a dispatcher chose them (ADR-029)."""
    slack = math.floor(slack_minutes)
    reasons = [
        Reason(
            ReasonCode.FORCED_ASSIGN,
            {
                "job_id": job.id,
                "technician_id": tech.id,
                "travel_minutes": round(travel_minutes),
                "slack_minutes": slack,
                "bumped_count": bumped_count,
            },
        )
    ]
    if label == SlaLabel.AT_RISK:
        reasons.append(Reason(ReasonCode.SLA_AT_RISK, {"slack_minutes": slack}))
    elif label == SlaLabel.BREACH:
        reasons.append(Reason(ReasonCode.SLA_BREACH, {"late_minutes": -slack}))
    return Explanation(tuple(reasons))


def forced_sentence(explanation: Explanation, job_label: str, tech_label: str) -> str:
    """Plain English over the facts of `explain_forced`."""
    forced = _first(explanation, ReasonCode.FORCED_ASSIGN)
    assert forced is not None, "a forced assignment always carries FORCED_ASSIGN"
    breach = _first(explanation, ReasonCode.SLA_BREACH)
    at_risk = _first(explanation, ReasonCode.SLA_AT_RISK)
    if breach:
        timing = f"will arrive {breach['late_minutes']} min after the deadline"
    elif at_risk:
        timing = f"will arrive with only {at_risk['slack_minutes']} min to spare"
    else:
        timing = f"will arrive with {forced['slack_minutes']} min to spare"
    parts = [
        f"“{job_label}” was given to {tech_label} by a dispatcher: {forced['travel_minutes']} min away, {timing}."
    ]
    n = int(forced["bumped_count"])
    if n:
        parts.append(
            f"To make room, {n} lower-priority job{'s were' if n != 1 else ' was'} sent back to the queue."
        )
    return " ".join(parts)


def explain_unassigned(
    job: JobView, rejected: Iterable[Rejection], technicians_checked: int
) -> Explanation:
    """Why nobody got this job. Expected outcome, not an error."""
    head = Reason(
        ReasonCode.NO_FEASIBLE_TECHNICIAN,
        {"job_id": job.id, "technicians_checked": technicians_checked},
    )
    return Explanation((head, *(r.reason for r in rejected)))


# ---- plain English ----------------------------------------------------------
def _first(
    explanation: Explanation, code: ReasonCode
) -> Mapping[str, int | float | str] | None:
    for reason in explanation.reasons:
        if reason.code == code:
            return reason.facts
    return None


def assignment_sentence(
    assignment: Assignment, job: JobView, technicians: Mapping[int, TechView]
) -> str:
    label = technicians[assignment.technician_id].label
    why = assignment.explanation
    chosen = _first(why, ReasonCode.ASSIGNED)
    assert chosen is not None, "an assignment always carries an ASSIGNED reason"

    breach = _first(why, ReasonCode.SLA_BREACH)
    at_risk = _first(why, ReasonCode.SLA_AT_RISK)
    if breach:
        timing = f"would arrive {breach['late_minutes']} min after the deadline"
    elif at_risk:
        timing = f"would arrive with only {at_risk['slack_minutes']} min to spare"
    else:
        timing = f"would arrive with {chosen['slack_minutes']} min to spare"

    parts = [
        f"{label} was chosen for “{job.label}”: {chosen['travel_minutes']} min away, {timing}."
    ]
    if int(chosen["candidates"]) > 1:
        parts.append(
            f"Best of {chosen['candidates']} available technicians ({chosen['strategy']} strategy)."
        )
    if _first(why, ReasonCode.SAME_SITE):
        parts.append(f"{label} already has a job at this location.")
    order = _first(why, ReasonCode.STOP_ORDER)
    if order and int(order["stops"]) > 1:
        where = (
            "first stop"
            if order["previous_job_id"] == 0
            else f"stop {order['stop']} of {order['stops']}"
        )
        parts.append(
            f"It is {where} of this run, {order['drive_minutes']} min from the previous point."
        )
        if order["reordered"]:
            parts.append("The run was reordered to cut driving time.")
    over = _first(why, ReasonCode.URGENT_OVER_LIMIT)
    if over:
        others = (
            "no technician under the limit could take it"
            if over["under_limit_candidates"] == 0
            else "technicians under the limit would arrive later"
        )
        parts.append(
            f"{label} already has {over['assigned_count']} jobs today (limit {over['limit']}),"
            f" but this job is urgent and {others}."
        )
    return " ".join(parts)


def _why_not(reason: Reason, label: str) -> str:
    facts = reason.facts
    if reason.code == ReasonCode.UNAVAILABLE:
        return f"{label} is unavailable"
    if reason.code == ReasonCode.SKILL_MISMATCH:
        return f"{label} does not have a matching skill"
    if reason.code == ReasonCode.DAILY_LIMIT:
        return f"{label} has reached the daily limit of {facts['limit']} jobs"
    if reason.code == ReasonCode.AFTER_CLOSING:
        return (
            f"{label} would arrive {facts['minutes_after_closing']:g} min after closing"
        )
    return f"{label}: {reason.code}"


def unassigned_sentence(
    unassigned: Unassigned, job: JobView, technicians: Mapping[int, TechView]
) -> str:
    head = _first(unassigned.explanation, ReasonCode.NO_FEASIBLE_TECHNICIAN)
    assert head is not None, (
        "an unassigned job always carries a NO_FEASIBLE_TECHNICIAN reason"
    )
    if head["technicians_checked"] == 0:
        return f"There are no technicians to assign “{job.label}” to."
    clauses = [
        _why_not(reason, technicians[int(reason.facts["technician_id"])].label)
        for reason in unassigned.explanation.reasons
        if reason.code != ReasonCode.NO_FEASIBLE_TECHNICIAN
    ]
    return f"No technician can take “{job.label}”: " + "; ".join(clauses) + "."
