# Design and testing

## Architecture

### Dispatch engine: input and output types

The engine (`backend/dispatch_engine/`) is a pure module: standard library only,
enforced by `lint-imports`. It speaks only in the types in `types.py`; the
adapter in `api/adapters.py` turns Django models into these types and back.

| Type | Holds | Why |
|---|---|---|
| `Location` | lat, lng (validated range) | shared by jobs, technicians, the workstation, distance |
| `JobView` | id, label, location, urgency, created_at, slot (none only if urgent), duration, acceptable skill ids | what FILTER, SCORE and ASSIGN need about a job |
| `TechView` | id, label, skill ids, shift start and end, availability, `free_at`, `position`, assigned count | `free_at` and `position` let a second planning run account for jobs already assigned |
| `OrgConfig` | workstation, scoring strategy, speed, urgent buffer, at-risk threshold, daily job target | one place for the organization's planning settings |
| `Assignment`, `Unassigned`, `Plan` | the result: who got which job, who did not, and why | an unassigned job is an expected outcome, not an error |
| `Reason`, `Explanation` | reason codes with numbers; the sentence is built later | the structured reasons are the explanation of record |

Rules the types enforce, because a wrong plan is worse than a crash:
- All times are timezone-aware. The adapter converts organization-zone shifts to
  absolute times, so the closing-time gate (ADR-012) is a plain comparison.
- A non-urgent job must have a slot (invariant 7); a slot ends after it starts.
- Speed must be positive (distance divides by it); risk is between 0 and 1.
- Types are frozen, so inputs cannot change under the engine (invariant 14).
- No customer name, phone or address enters the engine.

### Clock and distance
- `Clock` (`SystemClock`, `FixedClock`) is injected, so the same input and a
  fixed time give the same plan. The engine reads it once per run.
- `DistanceProvider` (`HaversineProvider`) gives miles and travel minutes
  (ADR-006). Straight-line distance, times a road factor of 1.3 for travel time.


### Filter rules
For one job, each technician is checked in this order; the first failure is
the single reason recorded:
1. available;
2. shares at least one skill with the job (any-of, invariant 2);
3. estimated arrival no later than shift end (ADR-012), inclusive.

Estimated arrival is the latest of now, the technician's free time and shift
start, plus travel. For a job with a slot it is never earlier than the slot
opening. Results are in id order and do not depend on input order.

### Job order and priority
Jobs are assigned in this order: urgent first, then priority (high before
low), then earliest deadline, then id. Earliest-deadline order keeps each
technician's day moving forward in time. A job's window is fixed (agreed with
the customer) or movable ("anytime that day", opening hours). Priority orders
jobs; it is not used to pick the technician.