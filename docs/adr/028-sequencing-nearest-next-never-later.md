# ADR-028: Sequence each technician's day nearest-next, and never make it later

Date: 2026-11-26 · Status: Accepted · Builds on ADR-027

## Context
ASSIGN (ADR-023) decides who does a job, and places each job in the earliest gap of
that technician's day (ADR-027), in the order it plans them. That order is by deadline, which keeps
people on time but ignores driving: with three wide windows a technician can be
sent to the far side of town, back to the middle, then next to the office. A
dispatcher sees that as a bad route even though nobody is late. The map also had
route lines only on the plan page, not on the main dispatcher map.

## Decision
A pure SEQUENCE stage (`dispatch_engine/sequencing.py`) runs after ASSIGN, per
technician, over that run's new jobs only. Jobs already Assigned or Ongoing are fixed
commitments (invariant 12, ADR-027): sequencing fits new jobs into the gaps between
them through the same `filtering._arrival` that ASSIGN uses, so a reorder never
moves an existing job and never lands on top of one.

1. At each step the candidates are the jobs that are slot-feasible: going to one
   does not make the rest of the day later than following the deadlines would.
2. An urgent job goes first when it is a candidate.
3. Otherwise the nearest candidate that needs no waiting for its window wins. If
   every candidate would wait, the one reached soonest wins. Ties: earlier
   deadline, then id.
4. The first stop is therefore the job nearest the technician's start (the
   workstation on a fresh day), unless its window does not allow going first.
5. Safety net: the new order replaces ASSIGN's order only when it is no later in
   total and drives less. Sequencing therefore cannot make a day worse.

Arrival times, slack and the SLA label are recomputed for the new order, and the
stored explanation is restated from them (new `stop_order` reason: stop number,
previous job, drive minutes, whether the run was reordered). `sequence_position`
is the stop number over the technician's whole day, in the order it runs, so a new job
placed in a gap before an existing job is numbered before it and the existing job's
number moves up (only its stop number changes, never its technician, time or status). `GET /map/jobs/` now carries `sequence_position` and
`scheduled_date`, and the dispatcher map draws one line per technician and day,
joining Assigned and Ongoing stops in stop order, the same way the plan page does.

## Alternatives considered
- **Pure nearest-neighbour with no feasibility check**: can send a technician to a
  near job that takes an hour and make a tight job late. It would need a repair
  step afterwards, which is harder to explain (ADR-003).
- **Joint assign and sequence**: closer to optimal, much harder to test and explain
  (ADR-002).
- **Road-following lines from a routing service (OSRM, OpenRouteService)**: they
  look better, but add a network dependency with usage limits and no change to the
  order. Parked; the lines are drawn straight and labelled as such.

## Trade-offs
- Still greedy: nearest-next can miss a better global order (the classic case is a
  line of stops where going to the nearest one first costs more driving overall).
  The safety net keeps ASSIGN's order in that case, so the cost is a missed
  improvement, never a worse day.
- **TIME:** the choice is greedy per technician and checks the drive to the next
  commitment only, as ADR-027 does. Full fidelity: choose the order and the gaps
  together over the whole day (S3c with an exact or local-search solver).
- Travel is straight-line distance times a road factor (ADR-006), so "nearest" is
  an estimate.
