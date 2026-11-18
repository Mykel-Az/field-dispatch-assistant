# ADR-023: Plan in deadline order, and never choose a late technician when another is on time

Date: 2026-11-18 · Status: Accepted

## Context
In the demo day, "Rooftop unit swap" (arrive 09:00-12:00, 3 h, high priority) was
planned before "Panel inspection" (arrive by 11:00, 1 h). The rooftop job took the
technician's morning and Panel was planned for 13:02, 123 minutes late, although
Rooftop could have waited until 11:30. The cause was the order: ADR-020 handled
jobs by priority first, so a wide window beat a tight one. A second weakness:
SCORE only added a late arrival to a weighted cost, so travel or load could
outweigh it and a late technician could be chosen while another was on time.
(Part of the demo's lateness was also the local fake geocoder, which scattered
addresses over 70 miles; it now stays inside one city.)

## Decision
1. **Two passes.** Pass 1 is the ADR-020 order (urgent, priority, deadline, id) and
   decides which jobs get a place when capacity is short. Pass 2 plans only the
   jobs pass 1 placed, in deadline order (urgent, deadline, priority, id), so each
   technician's day runs forward in time. Pass 2 is used when it places every
   one of them and leaves no more total lateness than pass 1; otherwise pass 1
   stands. Who was left out, and why, always comes from pass 1.
2. **Late is a last resort.** In SCORE, a technician who would miss the window is
   ranked after every technician who would not, whatever the costs. If everyone
   would be late, the lowest cost still wins and the job is assigned and flagged.
3. **Overlap is not special.** Two fixed jobs that overlap simply push the second
   arrival later on the same technician, which is a late arrival, so rule 2 sends
   them to different technicians when possible. Overlapping windows with room to
   follow each other (Panel by 11:00, then Rooftop by 12:00) stay on one technician.
4. **A decision trail.** The engine logs each pass at DEBUG (order, feasible,
   rejected with codes, ranking, choice, whether pass 2 was used) with ids and
   numbers only (ADR-019). `PLANNER_LOG_LEVEL=DEBUG` turns it on in a running
   server, and `manage.py plan_trace` shows it for one day and saves nothing.

## Alternatives considered
- **Deadline order only**: simplest and best for lateness, but a high-priority
  job with a wide window loses its place to a normal one with a tight window when
  the daily limit binds. Priority would stop doing its one job.
- **Fixed jobs first, flexible jobs after**: wrong in the demo (both are fixed),
  and a fixed window can be wide.
- **A lateness penalty large enough to always win**: a magic number that hides
  the rule. A rank is explicit and testable.

## Trade-offs
- Still greedy: a job is appended to the end of a technician's day. It cannot
  slot a short job into a gap before a long one, and it cannot see that a
  different pairing would help a later job. Pass 2 repairs the common case only.
- Pass 2 runs the pipeline twice; the cost is small (jobs x technicians per day).

## S3c hook (available_slots)
The single place that decides "when could this technician start this job" is
`filtering._arrival`, which today uses one number, `free_at`. S3c replaces `free_at`
with the technician's busy intervals and makes `_arrival` return the earliest gap
that fits the job's duration inside its window. The same function then answers
`available_slots()` (which times can be offered to a customer) and lets ASSIGN
insert a job into a gap. Rules 2 and 3 do not change: they read the slack that
`_arrival` produces.
