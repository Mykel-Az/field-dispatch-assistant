# ADR-022: The daily limit is a hard cap for planned work

Date: 2026-11-15 · Status: Accepted · Supersedes the "soft preference" sentence in ADR-012

## Context
ADR-012 made `max_jobs_per_tech_per_day` a soft preference. In practice a soft
number is invisible: the planner quietly gave someone five jobs and nobody could
tell why. The business wants to say "three a day" and have that hold, except in
an emergency.

## Decision
The limit is set per organization (`max_jobs_per_tech_per_day`, 1-10, default 3).

- **Normal jobs:** FILTER rejects a technician who is at the limit, with the
  reason `daily_limit`. The planner never exceeds it.
- **Urgent jobs:** may exceed it. ASSIGN prefers a technician under the limit,
  and uses one at the limit only when every under-limit candidate would give a
  strictly worse SLA outcome (ok, at risk, breach), or none is under the limit.
  The explanation says so (`urgent_over_limit`).
- Emergencies count toward a technician's load for the rest of the day.
- **Assigning by hand has no limit.** The dispatcher decides; the screen warns
  ("Sam already has 3 jobs that day (limit 3)") but does not block.

The old `over_target` scoring weight is gone: the cap replaces it.

## Alternatives considered
- **Keep it soft**: not explainable, and not what the business asked for.
- **Block manual assignment too**: removes the dispatcher's judgment and makes
  the tool unusable on a day with a real emergency.

## Trade-offs
- A hard cap can leave work unassigned when the day is full. That is the point:
  the plan says so, with a reason, instead of overloading someone.
- Counting only jobs already on a technician's day (TIME): a job assigned by
  hand counts, a job on a different day does not.
