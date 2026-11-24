# ADR-004: Explicit job lifecycle with append-only status history

Date: <fill in> · Status: Accepted

## Context
Dispatching, replanning, the technician page and the audit trail all depend on
a precise definition of what state a job is in and what can happen next.

## Decision
Statuses: Unassigned → Assigned → Ongoing → Completed / Incomplete / Failed /
Canceled.
- Completed, Failed and Canceled are terminal and never re-enter the queue.
- Incomplete is the only non-terminal outcome. It returns to the queue with a
  recorded reason.
- Every change must match an edge in the state-transition table (State
  pattern). Anything else is rejected with 409/422.
- `JobStatusHistory` is append-only, one row per status change.
- Updates are idempotent (e.g. `/arrive`) and concurrent edits are caught by
  a `version` column (optimistic locking, 409 on conflict).
- A partial unique index enforces one Ongoing job per technician.

## Who may move a job
Every edge has exactly one kind of caller. Technician endpoints only ever touch the
caller's own jobs; any other job, in any organization, answers 404 (not 403, so
ids are not revealed). Repeating an action answers 200 with the job as it is;
a job in the wrong state answers 409 `illegal_transition`.

| Move | Who | Through |
|---|---|---|
| Unassigned → Assigned | dispatcher, or the planner on their behalf | `POST /jobs/{id}/assign/`, `POST /schedule/generate/` |
| Assigned → Unassigned | dispatcher; the system when a technician is deactivated | `POST /jobs/{id}/unassign/` |
| Assigned → Ongoing | the assigned technician only | `POST /technician/me/jobs/{id}/arrive/` |
| Ongoing → Completed | the same technician | `POST /technician/me/jobs/{id}/complete/` |
| Ongoing → Incomplete → Unassigned | the same technician, reason required | `POST /technician/me/jobs/{id}/incomplete/` (two history rows) |
| Unassigned or Assigned → Canceled | dispatcher, reason required | `POST /jobs/{id}/cancel/` |
| Ongoing → Failed | nobody yet: the edge exists, no endpoint (Sprint 3 if needed) | none |

A second Arrive while another job is Ongoing is refused with 409
`another_job_ongoing`. The technician's row is locked first, so two requests take
turns; the partial unique index is the backstop.

## Alternatives considered
- **Free-form status field**: easy, but invalid states become possible and the
  explanation/audit story disappears.
- **Event sourcing**: powerful, but far beyond what this project needs.

## Trade-offs
- More code up front (transition table, history writes). In return the
  invariants become testable at the DB and API level.

## Amendment (2026-11-24): edits are history too
History was status changes only, so changing a job's address, priority or window left
no trace. Edits now add one row per save (`kind="edit"`, `changes` = `{field:
[before, after]}`, skills by name). A save that changes nothing adds nothing. A pin
or a re-lookup of the location adds a `location` change. Edit rows keep the job's
status in `from_status` and `to_status` and have no reason. Status rows are
`kind="status"`; the "last two status rows" logic ignores edit rows. The history
visible to dispatchers can hold customer details; it never reaches the engine
(ADR-019).

