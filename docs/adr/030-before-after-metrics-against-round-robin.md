# ADR-030: Measure the plan against a round-robin baseline

Date: 2026-11-27 · Status: Accepted · Implements the Sprint 3 before/after metrics

## Context
"The planner is better" is a claim. A dispatcher, and the capstone reviewer, need a
number they can check. Before software, small shops hand out work in turn: the next
job goes to the next technician who can do it.

## Decision
`GET /schedule/metrics/?date=` (dispatchers only) takes the day's placed jobs (Assigned,
Ongoing or Completed with a technician) and measures them twice:
- **Planner**: the technicians and stop order the system actually produced.
- **Baseline**: the same jobs dealt out round-robin in request-id order, only to
  technicians who have an acceptable skill, in the order dealt. It ignores distance,
  load, priority and deadlines, which is what "in turn" means.

Both are timed from the start of the day with an empty workload, using the engine's
own arrival and deadline rules (`dispatch_engine/metrics.py`, pure, no customer data,
ADR-019). Each side reports jobs placed, jobs that could not be placed, SLA breaches,
minutes late, miles driven, and workload spread (most jobs minus fewest). Jobs the
engine left in the queue are counted separately as `in_queue` and are in neither side.
The plan page draws one card per measure (late arrivals, minutes late, driving, uneven
workload) with two bars, planner and round-robin, scaled against each other, and a plain
verdict ("Planner is better", "Round-robin is better", "Same") with a glyph so it is not
colour alone. A headline counts the measures the planner wins. A table of numbers was
tried first and replaced: it was hard to scan and did not suit a dispatcher glancing at it.

## Alternatives
- **Compare against random assignment.** Rejected: a strawman nobody uses.
- **Compare against a brute-force optimum.** Rejected: expensive, and not what a
  dispatcher would otherwise do.
- **Store a baseline each time the planner runs.** Rejected: it would drift from the
  data; computing both on read cannot disagree with it.

## Trade-offs
- Replaying the day from its start ignores what has already happened (a job that ran
  long). It measures the quality of the plan, not the day's outcome. **TIME.** Full
  fidelity: record actual start and finish times and compare those.
- Straight-line distance, as everywhere else (ADR-004).
- The baseline is one reasonable "before". Another shop's habits would differ.

## Result on the demo data (run on 2026-11-27, four days, 8 placed jobs each)
| Day | SLA breaches (planner / baseline) | Minutes late | Miles driven |
|---|---|---|---|
| 1 | 1 / 1 | 208 / 90 | 54.2 / 58.0 |
| 2 | 1 / 3 | 32 / 292 | 52.3 / 46.4 |
| 3 | 0 / 4 | 0 / 243 | 64.1 / 52.1 |
| 4 | 0 / 2 | 0 / 138 | 37.8 / 31.1 |

The planner wins on lateness on three of four days. It does **not** drive fewer miles
on most of them: it spends distance to meet windows and to keep the load even
(spread 0, against 2 for the baseline on two days). Day 1 is a day the baseline does
better on lateness. These numbers are reported as measured.
