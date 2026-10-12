# ADR-008: Service-layer functions for business writes

Date: <fill in> · Status: Accepted

## Context
Slot booking, assignment and replanning must be atomic and race-safe. Putting
that logic in views or serializers makes it hard to test and easy to bypass.

## Decision
- `api/services/` (scheduling, jobs, events) holds all business writes, each
  wrapped in `transaction.atomic()` with `select_for_update()` where rows
  contend (replan, slot booking re-validated under lock).
- Serializers validate input only. Views stay thin.
- `api/adapters.py` is the only file that imports both engine dataclasses and
  Django models, so `dispatch_engine/` stays framework-free (enforced in CI
  by import-linter).

## Alternatives considered
- **Fat models / signals**: logic is scattered and implicit.
- **Logic in views/serializers**: couples business rules to HTTP.

## Trade-offs
- One more layer to navigate. In return the services are testable against a
  real Postgres in CI, including concurrency cases.
