# ADR-027: New jobs fit in the gaps between a technician's fixed jobs

Date: 2026-11-26 · Status: Accepted · Amends ADR-026 (replaces its "TIME" shortcut)

## Context
In production a dispatcher had assigned a fixed 2–4 pm breaker job to Aisha. At
9 am he planned an urgent AC job. The planner put it at 4:11 pm, marked
"Late · 480 min late". Two things looked wrong and both were real:
- **"Late" on a job with no time window.** An urgent job has no customer window, but
  it carries the company's own promise (`URGENT_BUFFER_MINUTES`, 60): arrive within an
  hour of the job being logged, or of the day opening. That deadline was about 8:11
  am; 4:11 pm is 480 minutes after it. The 11 minutes is the drive, not the wait.
- **Why not first?** ADR-026 made existing jobs hold the technician, but only as
  "busy until the last one ends". New jobs could only go *after* everything, never in
  the free hours before a fixed job.

## Decision
1. A technician's Assigned and Ongoing jobs are **commitments**: start, end,
   place. They are fixed; the planner never moves them.
2. To place a job, FILTER walks the commitments in time order and takes the first
   gap that holds the **drive in, the job, and the drive on to the next commitment**
   (`arrival + duration + drive <= next.start`), counting from the later of now and
   the start of their shift, starting at the workstation. If no gap fits, the job goes after the
   last commitment, from that job's place.
3. A job with a customer window never starts before the window opens; the gap is
   checked at that arrival, not earlier.
4. Each job ASSIGN places becomes a commitment for the next job in the same run,
   so two new jobs share one gap one after the other.
5. Everything else is unchanged: an arrival after closing is still refused, the
   daily limit still applies, and lateness still ranks a candidate after an on-time one.

## Alternatives considered
- **Re-order the whole day (true sequencing)**: could pull the 2 pm job earlier or
  later. Fixed jobs are promises to customers; moving them is Sprint 3 sequencing
  and a dispatcher's call.
- **Pull only urgent jobs forward**: a normal job in a gap is equally right; the
  rule is about time, not urgency.

## Trade-offs
- TIME: a commitment's start is the planned arrival, else the start of the customer's
  window, else now. A hand-assigned any-time job with no estimate therefore blocks
  from now. Full fidelity: store an estimate when a job is assigned by hand.
- TIME: drive time is checked to the next commitment only, not further on.
- Greedy: the first gap that fits wins, not the best use of the day (gap choice
  with total travel is Sprint 3 sequencing, S3c).
