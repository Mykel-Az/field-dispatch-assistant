# ADR-012: Closing time as the single hard feasibility gate

Date: <fill in> · Status: Accepted

## Context
Several overlapping rules (minute-based capacity, job-count limits, closing
time) made feasibility ambiguous and hard to test.

## Decision
One hard gate: `estimated_arrival <= shift_end`. A technician may start a job
any time before closing and finish it after closing, but may not start a new
job after closing. Capacity in minutes only feeds `estimated_arrival`.
`max_jobs_per_tech_per_day` (default 3–4) is a soft preference in ASSIGN, not
a hard cap. A last job running past closing is normal. Overrun triggers
re-estimate or replan only when it pushes later jobs on the same day.

## Alternatives considered
- **Hard cap on jobs per day**: simple, but rejects feasible work.
- **Separate capacity filter plus closing time**: two gates, harder to test.

## Trade-offs
- Technicians may occasionally work past closing. Accepted and visible in the
  plan. Invariant #5 (never start a new job after shift_end) is testable as a
  property.
