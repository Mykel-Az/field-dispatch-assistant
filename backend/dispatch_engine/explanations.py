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
    if chosen.sla_label == SlaLabel.AT_RISK:
        reasons.append(Reason(ReasonCode.SLA_AT_RISK, {"slack_minutes": slack}))
    elif chosen.sla_label == SlaLabel.BREACH:
        reasons.append(Reason(ReasonCode.SLA_BREACH, {"late_minutes": -slack}))
    if tech.assigned_count >= config.max_jobs_per_tech_per_day:
        reasons.append(
            Reason(
                ReasonCode.OVER_DAILY_TARGET,
                {
                    "technician_id": tech.id,
                    "assigned_count": tech.assigned_count,
                    "target": config.max_jobs_per_tech_per_day,
                },
            )
        )
    # Keep why the others could not take it: this is what "why not technician X?" needs.
    reasons.extend(r.reason for r in rejected)
    return Explanation(tuple(reasons))


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
    over = _first(why, ReasonCode.OVER_DAILY_TARGET)
    if over:
        parts.append(
            f"{label} already has {over['assigned_count']} jobs today (target {over['target']})."
        )
    return " ".join(parts)


def _why_not(reason: Reason, label: str) -> str:
    facts = reason.facts
    if reason.code == ReasonCode.UNAVAILABLE:
        return f"{label} is unavailable"
    if reason.code == ReasonCode.SKILL_MISMATCH:
        return f"{label} does not have a matching skill"
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
