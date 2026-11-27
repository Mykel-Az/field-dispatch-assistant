# ADR-031: Restate the day when a job runs over; plan again when a technician drops out

Date: 2026-11-27 · Status: Accepted · Builds on ADR-026, ADR-028

## Context
A plan is a promise about arrival times. Two things break it during the day: a job runs
longer (or shorter) than estimated, and a technician becomes unavailable. The customer
and the dispatcher need to see the truth, but silently moving jobs between technicians
would be worse than a late arrival: the dispatcher knows things the system does not.

## Decision
**Overrun re-estimate.** When a technician completes a job, or returns it incomplete,
the system restates the arrival time, slack and label of their remaining Assigned stops
for that day (`dispatch_engine/replanning.reestimate`, called through
`scheduling.reestimate_after_finish`). The technician is free now, at the address they
just left, and drives to each remaining stop in its existing order.
- Only times, slack and labels change. The technician and the stop order never do
  (invariant 13); a stop that is now late shows as late or at risk and the dispatcher
  decides what to do.
- It is not an edit: the job's `version` does not change, so a dispatcher editing the
  same job is not told it is stale. Started jobs and other technicians' jobs are not read
  or written.
- An early finish pulls later stops sooner by the same rule.
- It runs after the technician's own action has been saved. If it fails, the failure is
  logged and the technician's action stands: restated times are a courtesy.
- A job that overran when it was the day's last has no later stop, so nothing changes.

**A technician who becomes unavailable.** Deactivating a technician already returns
their Assigned jobs to the queue with a history reason (ADR-004, ADR-017); jobs under way block
deactivation. Those jobs are planned again by the one planner button. Nothing is moved
automatically.

## Alternatives
- **Re-plan the whole day on every overrun.** Rejected: it would reshuffle jobs
  between technicians behind the dispatcher's back and change times customers have
  been told.
- **Re-sequence the technician's remaining stops.** Rejected for now: reordering is a
  promise change too; the dispatcher can press Plan again.
- **Do nothing and let the day drift.** Rejected: the dispatcher would find out when
  the customer calls.

## Trade-offs
- The new times use the planned duration of each remaining job, not how long the last
  job actually took. **TIME.** Full fidelity: learn each technician's pace per category.
- Straight-line drive times, as everywhere (ADR-004).
- The restated slack is stored in the job's explanation; the original reasons and
  sentence are kept as the planner wrote them.
