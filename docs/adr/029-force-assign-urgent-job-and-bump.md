# ADR-029: Force-assign an urgent job, bumping what stands in the way

Date: 2026-11-27 · Status: Accepted · Implements ADR-011

## Context
A no-heat call for an elderly customer cannot wait for the next planning run, and the
technician who can get there fastest may already be booked solid. Dispatchers do this
by phone today: "Dana, drop the filter swap and go to this one." The system has to let
a dispatcher make that call, show what it costs before they commit, and never leave a
job lost or a day inconsistent.

## Decision
`POST /jobs/{id}/force-assign/` gives an urgent, Unassigned job to a technician the
dispatcher chose. The pure rule lives in `dispatch_engine/bumping.py`; the writes in
`api/services/scheduling.force_assign`.
- If the technician reaches the job by its deadline (the urgent SLA, ADR-022), nothing
  else changes.
- If not, jobs they have **not started** are sent back to the queue, one at a time,
  until it fits. Only a bump that brings them there sooner is made, so a low-priority
  job that is not in the way stays. The one to go first is the lowest priority, then
  the one with the most slack, then the lowest id.
- Never bumped: a job already Ongoing, and any other urgent job. This is the named
  exception to the frozen-job rule (invariant 12): a forced assignment may release an
  Assigned job, but never one that has started.
- Not finding a way to make it is an expected outcome, not an error: the job is
  assigned anyway and shown as late, with a warning in the dialog.
- `dry_run: true` runs the same calculation and writes nothing. The dialog calls it
  first so the dispatcher sees the arrival time and the titles of the jobs that go back,
  then confirms.
- It runs under the same organization lock as a planner run, then locks the
  technician's day, so two force-assigns, or one and a plan, take turns.
- Bumped jobs get a history row naming the urgent job; the urgent job gets an
  explanation (`forced_assign`) in the same structured form as the planner's. The
  technician's whole day is then renumbered in clock order (ADR-028).

## Alternatives
- **Preempt automatically** when an urgent job arrives. Rejected: choosing whose day
  to disturb is a judgement about customers, not a calculation.
- **Bump the lowest priority regardless of whether it helps.** Rejected: it would
  disrupt a customer for nothing.
- **Plan the bumped jobs again straight away.** Rejected: a plan run would also place
  other unassigned jobs the dispatcher has not looked at. The bumped jobs wait in the
  queue and the dispatcher presses Plan.

## Trade-offs
- The bump choice is greedy (one job at a time), not the least disruptive set.
  **TIME.** Full fidelity: choose the smallest set of jobs, weighted by customer impact.
- The urgent job's own explanation is stored; a bumped job's is cleared when it returns
  to the queue (as for any job), and its history row carries the reason.
