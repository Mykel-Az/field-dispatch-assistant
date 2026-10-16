# ADR-010: Week-ahead slot booking lookahead (planning stays per-day)

Date: <fill in> · Status: Accepted

## Context
Customers should be able to book the earliest suitable appointment, possibly
days ahead, but the dispatcher view only shows today and tomorrow.

## Decision
`available_slots()` looks up to one week ahead and reuses the FILTER stage.
Per-day ASSIGN + SEQUENCE is unchanged. A stored `scheduled_date` on Job
supports this and gives a plain UniqueConstraint on
(technician, scheduled_date, sequence_position). Urgent jobs bypass slots.

## Alternatives considered
- **Joint multi-day route optimisation**: higher cost and risk, and it
  contradicts the earlier "no multi-day calendars" scope decision.

## Trade-offs
- Days are planned independently, so weekly workload may be less balanced
  than a joint plan would give. Accepted and documented.

> **Amendment (TIME):** lookahead is reduced from one week to today +
> tomorrow. Full-fidelity path: one-week lookahead as originally decided.