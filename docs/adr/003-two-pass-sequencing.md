# ADR-003: Two-pass sequencing with slot-aware reconciliation

Date: <fill in> · Status: Accepted

## Context
Assignment decides *who* does a job; sequencing decides *in what order*. Jobs
also have fixed appointment slots, so pure nearest-neighbour ordering can
produce a route that breaks a slot.

## Decision
Two passes. Pass 1 assigns jobs to technicians (ADR-002). Pass 2 sequences
each technician's day. At each step, Sequence considers only slot-feasible
candidate jobs; among those, the nearest wins. The first stop is the job
closest to the Workstation, unless its slot does not allow going first, in
which case the earliest slot-feasible-by-distance job goes first.

## Alternatives considered
- **Order by distance only, then repair slot violations**: simpler, but
  repairs can cascade and are hard to explain.
- **Joint assign + sequence in one pass**: closer to optimal, but much harder
  to reason about, test and explain.

## Trade-offs
- Greedy, so it can miss better global orderings. Accepted (ADR-002).
- Invariant #6 (no overlapping windows per technician) is testable as a
  property: for any generated input, sequenced windows never overlap.


## Amendment (Nov 4): what a slot means for planning

A slot is the appointment window agreed with the customer: the technician
arrives inside it, and the job may run past `slot_end`, which is the SLA
deadline. The planner never moves a fixed window earlier than `slot_start`,
and it changes only by customer decision or an external factor. A job with no
agreed time ("anytime that day") gets a movable window: the organization's
opening hours for that day, marked `slot_is_fixed = false`. Only movable jobs
may be rescheduled by the planner, and a replan proposes such moves to the
dispatcher rather than applying them.

**TIME:** Sprint 2 plans one pass in order of earliest deadline and does not
fill gaps. The full-fidelity path is sequencing with fixed windows as anchors
(Sprint 3). A per-job "customer must be present" setting is a further path.