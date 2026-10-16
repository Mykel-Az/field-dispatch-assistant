# ADR-016: Multi-tenancy with explicit organization scoping

Date: 2026-10-13 · Status: Accepted

## Context
The product serves several companies. One company must never read or change
another's data, and must not even learn that a record exists.

## Decision
Shared database, shared schema; every tenant row carries an `organization`
foreign key.
- Every user belongs to exactly one Organization. Registration creates the
  organization and its first head dispatcher.
- Scoping is explicit: `Model.objects.for_organization(org)`, a base ViewSet
  mixin that filters by `request.user.organization`, and services that take
  `organization` as an argument. No thread-locals.
- Another organization's object returns 404; wrong role returns 403 (role is
  checked before object lookup); unauthenticated returns 401. A same-org
  technician asking for another technician's job gets 404.
- Skill, CandidateSkillRule and GeocodeCache are global, not tenant-scoped.
- The engine receives per-organization configuration as plain data and never
  imports Organization.
- Safety net: an enumeration test hits every tenant-model endpoint as an
  org-B user and expects 404; a route-introspection test fails if a view
  declares no permission.

## Alternatives considered
- **Schema-per-tenant (django-tenants) / database-per-tenant**: strongest
  isolation, but migrations, connection handling and the single free Neon
  database make it costly to operate.
- **Postgres row-level security**: good defence in depth; needs per-request
  session variables. Documented upgrade, not built (TIME).
- **Thread-local current tenant + auto-filtering manager**: invisible global
  state; it breaks silently in background work and tests, and a forgotten
  reset leaks data across tenants.

## Trade-offs
- A forgotten `for_organization` is a leak. Mitigation: the mixin is the only
  way views get querysets, plus the enumeration test in CI.
- Cross-tenant foreign keys are prevented in services and by tests. A
  database-level composite foreign key is the full-fidelity path (TIME).
- Global tables mean one organization cannot define private skills. Upgrade:
  an organization-scoped skill table.
