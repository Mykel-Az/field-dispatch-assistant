# ADR-026: New jobs are planned around what a technician already has

Date: 2026-11-24 · Status: Accepted · Amends ADR-023 and ADR-004

## Context
Three manual-test findings, one cause. (1) A dispatcher assigned a 14:00–16:00
job to Aisha by hand, then ran the plan for an urgent job at 15:00. The planner
treated Aisha as free at the workstation and told the customer she would arrive 89
minutes late, because it had not seen the job she was on. (2) A job assigned by
hand disappeared from the plan page. (3) Switching Balanced to Nearest and running
again changed nothing, because Run plan only touches unassigned jobs and after the
first run there are none.

## Decision
1. **Existing jobs hold the technician.** A technician's Ongoing and Assigned jobs
   for the day, whether the planner or a person assigned them, are walked in the
   order they will happen (`adapters._busy_chain`). Each starts at its planned
   arrival, else the start of the customer's window, but not before the previous job
   ends or before now. The technician is free when the last one ends and starts from
   that job's address, not from the workstation. A job whose time and window have
   both passed holds nobody.
2. **The plan page shows the whole day,** not only what the last run placed: every
   Assigned and Ongoing job with its technician, marked "Assigned by hand" when no
   planner arrival time exists, and on the map. A run no longer makes earlier jobs
   vanish.
3. **Plan again.** `POST /api/schedule/generate/` accepts `replan: true`: jobs the
   planner placed that have not started go back to the queue (a history row "Planned
   again", source planner) and are planned again, so a changed strategy or limit
   takes effect. Jobs assigned by hand and jobs under way stay. The plain Run plan
   is unchanged.
4. A job assigned by hand has no arrival time: it is returned that way (`null`), not
   guessed.

## Alternatives considered
- **Make Run plan always re-plan everything**: surprising; it would undo the plan
  technicians may already have been told.
- **Also re-plan hand-assigned jobs**: a dispatcher's decision is not the planner's
  to reverse.

## Trade-offs
- Existing jobs were first treated as "busy until the last one ends"; ADR-027 replaced
  that with real gaps, so new jobs can go before a later fixed job.
- Plan again can change an arrival time the technician has already seen. It is a
  button, not automatic, and it leaves a history row.
