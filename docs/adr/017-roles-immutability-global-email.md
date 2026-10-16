# ADR-017: Roles, immutability and globally unique email

Date: 2026-10-13 · Status: Accepted

## Context
Three kinds of people use an organization, and mistakes in who can do what
are security problems. Jobs and history refer to users as actors, so a user's
meaning must not change over time.

## Decision
- Roles: `head_dispatcher`, `dispatcher`, `technician`. A head can do
  everything a dispatcher can, plus user management and organization settings.
  Heads can create heads. A technician sees and changes only their own
  assigned jobs.
- Role and organization are immutable after creation and are never writable
  through any API (a request that tries gets 400). Enforced in the model
  `save()` and by tests. To change a role, deactivate and create a new user
  with a new email.
- Users are deactivated, never deleted (history keeps the actor).
  `reactivate` restores the same role in the same organization.
- Every organization always has at least one active head dispatcher
  (`select_for_update` on the Organization row in every head-affecting write).
- Login is by email only. Emails are lowercased and unique on `Lower(email)`
  across all organizations. Registration and creation answer "email
  unavailable" without saying where it exists; login failure is one generic
  message.
- A superuser lives outside tenants (organization NULL, allowed only when
  `is_superuser`, enforced by a CheckConstraint) and uses Django admin only.

## Alternatives considered
- **Promote/demote roles**: needs audit rules and re-validation of invariants
  on every change; privilege escalation surface.
- **Users in several organizations (membership table)**: right for
  contractors who work for two companies; large change to every query and to
  login. Upgrade path.
- **Per-organization email uniqueness**: needs organization selection at login.

## Trade-offs
- One email, one organization. A person working for two companies needs two
  emails.
- No role change without a new account, so history stays unambiguous.
- TIME: no invitation or password-reset emails. A head sets the initial
  password; a forgotten head password is reset by the platform superuser in
  Django admin. Upgrade: invitation + reset emails.
