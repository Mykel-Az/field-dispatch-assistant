# ADR-002: Heuristic pipeline instead of optimal (ILP) solving

Date: <fill in> · Status: Accepted

## Context
The core feature is planning a field-service day: which technician gets which
job, in what order, and what to do when the day changes. Dispatchers need to
understand and trust the result.

## Decision
A four-stage, deterministic pipeline in a pure module (`dispatch_engine/`):
FILTER (skill, hours, capacity, parts) → SCORE (SLA risk, distance,
workload) → ASSIGN + SEQUENCE (nearest-neighbour over real coordinates) →
REPLAN (on disruption). Every assignment carries a plain-English explanation.

## Alternatives considered
- **ILP / constraint solver (e.g. OR-Tools VRP)**: can find better routes, but
  is hard to explain, harder to test deterministically, and a large
  dependency for a 7-week solo project.
- **Naive round-robin**: trivial, but ignores skills, SLA and distance. Kept
  only as the baseline for the final benchmark.

## Trade-offs
- Routes are not provably optimal. Mitigation: benchmark against round-robin
  (SLA breaches, total travel, workload spread) and document the gap.
- Determinism (same inputs + config + tie-break → same output) makes
  property-based testing practical (Hypothesis).
- True optimal solving is explicitly out of scope and documented as such.
