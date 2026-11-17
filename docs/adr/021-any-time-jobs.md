# ADR-021: "Any time that day" jobs are a movable window

Date: 2026-11-15 · Status: Accepted

## Context
Some customers agree to a day, not a time. Forcing a dispatcher to invent a
window (say 9:00-11:00) makes the plan look rigid and the SLA numbers wrong:
the planner would call a 12:00 arrival "late" for a time nobody promised.

## Decision
`Job.slot_is_fixed` is true by default. An "any time that day" job is stored as
a window equal to the organization's opening hours on that day, with
`slot_is_fixed = false`. The engine already plans against a window, so it needs
no new rule: arrival can be anywhere inside the opening hours.

Clients do not send `slot_is_fixed`. They send either `slot_start`/`slot_end`
(fixed) or `any_time_on` (a date), and the server works the flag out. A
database constraint requires every non-fixed job to have a window.

While a job is unassigned its window follows the organization: if opening hours
or the time zone change, it is recomputed from the job's day. An assigned job
keeps the window it was planned in. Urgent jobs do not take a day.

## Alternatives considered
- **A null window meaning "anytime"**: every reader would need a special case,
  and invariant 7 (non-urgent jobs have a slot) would need a hole.
- **Let the client compute the window**: duplicates time-zone logic in the
  browser and drifts when opening hours change.

## Trade-offs
- The window is a snapshot of the hours at save time, refreshed on change for
  unassigned jobs only (TIME). Full fidelity would re-plan assigned jobs too.
- The engine does not yet move a flexible job to make room for a fixed one. The
  flag is stored and passed through so Sprint 3 sequencing can use it.
