# ADR-024: The time zone cannot change while jobs are Assigned or Ongoing

Date: 2026-11-19 · Status: Accepted · Amends [ADR-016](016-multi-tenancy-explicit-scoping.md) (organization settings)

## Context
Every job time and working hour is on the organization's clock (an IANA zone).
`scheduled_date` is the job's day on that clock, so "a job at 23:30 Chicago time"
is the 14th even though it is already the 15th in UTC. Changing the zone moves
the clock under work that people have already been told about: an Assigned job
has a plan, a technician's day, and a customer who was given a window; an
Ongoing job is happening now. Silently shifting those by hours would send a
technician to the right place at the wrong time.

## Decision
1. `scheduled_date` is always computed in the organization zone
   (`job_service.local_date`), never in UTC or the browser's zone.
2. A PATCH that changes `timezone` is refused with **409 `timezone_locked`** while
   any job of that organization is Assigned or Ongoing. The message says how many.
   The error body carries `code` so the page can tell it from a stale-version 409.
   Nothing is saved (the check runs before any field is written).
3. Allowed when no job is Assigned or Ongoing. Unassigned, Completed, Incomplete,
   Failed and Canceled jobs are not blocked. The existing `rederive_dates` then moves
   fixed jobs to their new local day and gives unassigned flexible jobs a new
   window (ADR-021). Re-sending the current zone is not a change.
4. The Organization page states the rule next to the field and shows the server
   message at the field when it is refused. The user's choice stays on screen.

## Alternatives
- **Allow it and re-plan everything**: surprises technicians and customers
  mid-day; plans are promises.
- **Allow it and keep each job's UTC moment**: correct instants, but the dispatch
  board's day grouping changes under the dispatcher's feet.
- **Block while any job is not finished**: too strict; a backlog of Unassigned
  jobs would make the zone permanently locked.

## Trade-offs
- TIME: the check counts live jobs without locking them. A job assigned in the
  same instant as the zone change can slip through. Full fidelity: take a shared
  lock on the organization row when a job becomes Assigned (in `transition`),
  with a fixed lock order against the organization PATCH, which already locks the
  organization row exclusively.
- A company that moves or mis-set the zone must first finish or unassign today's
  work. That is rare and the message says what to do.
