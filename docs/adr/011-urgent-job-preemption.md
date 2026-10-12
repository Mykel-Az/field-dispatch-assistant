# ADR-011: Urgent-job preemption by forced assignment

Date: <fill in> · Status: Accepted

## Context
Emergencies cannot wait for the next planning run, but a technician's day is
already full.

## Decision
The dispatcher force-assigns an urgent job to a chosen technician
(`POST /jobs/{id}/force-assign`). If that exceeds capacity, the system
auto-bumps that technician's lowest-priority / most-slack non-urgent job back
to the queue. A normal replan then runs on the rest of that technician's day.
Ongoing jobs are never touched.

This adds a named exception to the Frozen-job invariant (#12), alongside the
existing "unavailable technician" exception.

## Alternatives considered
- **Fully automatic urgent routing**: removes the human from a high-stakes
  decision and is harder to explain.
- **Never bump**: urgent jobs would wait or fail the SLA.

## Trade-offs
- Bumped customers get rescheduled; the explanation and status history record
  why. If no bump candidate exists, the failure is an expected outcome with a
  message, not an error.
