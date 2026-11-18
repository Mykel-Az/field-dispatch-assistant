# ADR-020: Job priority orders the work, it does not choose the technician

Date: 2026-11-15 · Status: Accepted

## Context
Dispatchers know some jobs matter more than others (a commercial client, a
repeat complaint) without those jobs being emergencies. Urgent already means
"start within the buffer, may break the daily limit" (ADR-011). Something softer
is needed, or dispatchers will mark everything urgent to get attention.

## Decision
`Job.priority` is `low`, `normal` (default) or `high`. It does one thing: the
order in which ASSIGN considers jobs. The order is urgent first, then priority
(high before low), then earliest deadline, then id. When capacity is short,
the jobs considered first get the places.

It does not change which technician is chosen (FILTER and SCORE ignore it), and
it never overrides the daily limit or a skill: a high-priority job nobody can
take stays unassigned, with the reason.

Priority can be edited at any status. It is not a plan field: changing it on an
assigned job does not move that stop.

Amended by ADR-023: this order decides who gets a place. The jobs that get one are
then planned in deadline order, so priority never makes a tight window late.

## Alternatives considered
- **A number (1-10)**: false precision; nobody can say what a 6 means.
- **Priority as a score weight**: mixes "who goes first" with "who is best for
  it", and makes explanations hard to read.
- **Reuse urgent**: loses the distinction, and urgent jobs may exceed the limit.

## Trade-offs
- A priority edit on an already-planned job has no effect until the next plan.
  Sprint 3 adds a suggestion ("this job is now high priority: re-plan the
  day?"), not an automatic re-plan, so people are never surprised by moved stops.
- Three levels are coarse on purpose.
