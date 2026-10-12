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

## Alternatives considered
- **Free-form status field**: easy, but invalid states become possible and the
  explanation/audit story disappears.
- **Event sourcing**: powerful, but far beyond what this project needs.

## Trade-offs
- More code up front (transition table, history writes). In return the
  invariants become testable at the DB and API level.
