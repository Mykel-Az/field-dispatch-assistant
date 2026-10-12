# ADR-001: Django + Django REST Framework for the backend

Date: <fill in> · Status: Accepted

## Context
The system is relational and constraint-heavy: a partial unique index (one
Ongoing job per technician), optimistic locking, row locks during assignment,
append-only history. It also needs authentication, role permissions, an admin
for seeding data, migrations, and an OpenAPI schema for the typed frontend.

## Decision
Django + DRF on PostgreSQL. drf-spectacular produces the OpenAPI schema.

## Alternatives considered
- **FastAPI**: less boilerplate, async, good OpenAPI. But ORM, migrations,
  auth and admin must be assembled (SQLAlchemy + Alembic + custom auth),
  which costs time I do not have.
- **Flask**: same assembly problem, with fewer conventions.

## Trade-offs
- DRF serializers are verbose. Mitigation: serializers do validation only;
  business logic lives in service functions (ADR-008). Separate list and
  detail serializers.
- N+1 queries are easy to write in the ORM. Mitigation: select_related /
  prefetch_related, plus `assertNumQueries` tests on list endpoints.
- Scale: pagination, indexes on status / technician / date, and a thin
  map-poll endpoint. The assignment run stays in-request at capstone scale.
  Moving it to a background worker is a documented scale path, not built.
