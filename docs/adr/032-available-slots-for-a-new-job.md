# ADR-032: Offer times for a new job (read-only available slots)

Date: 2026-11-27 · Status: Accepted · Builds on ADR-027

## Context
A customer on the phone asks "when could someone come?" The dispatcher should not have
to create a job, run the planner and undo it to find out. The planner already knows how
to fit a job into the gaps between a technician's fixed jobs (ADR-027).

## Decision
`GET /jobs/{id}/available-slots/?days=N` (dispatchers only, 1 to 14 days, default 7)
returns the earliest start per technician per day for that job's location, duration and
skills, soonest first. It books nothing and writes nothing.
- It uses the planner's own FILTER rules (available, has a skill, under the daily limit,
  arrives before closing) and gap-fitting arrival, through `dispatch_engine/slots.py`,
  so an offered time is one the planner would also accept.
- The job has no agreed time yet, so for each day its window is the organization's
  opening hours (ADR-021).
- Each day starts from the technicians' Assigned and Ongoing jobs as fixed commitments.
  The job's own current booking, if any, is ignored so it does not block itself.
- A job without a location answers 409.

## Alternatives
- **Offer fixed appointment windows (8-10, 10-12...).** Rejected: the planner works in
  minutes; rounding would hide gaps. **TIME** to build a booking layer.
- **Hold the slot while the customer decides.** Rejected: it needs expiry and
  concurrency rules for a feature that only answers a question.

## Trade-offs
- An offered time can be gone a minute later. The endpoint is advice, and assigning
  still goes through the planner or Assign, which check again.
- The time shown is the technician's earliest start, not a promise of an arrival window.
- No screen yet: the endpoint is the deliverable. **TIME.** Full fidelity: a slot picker
  on the job page that assigns the chosen technician.
