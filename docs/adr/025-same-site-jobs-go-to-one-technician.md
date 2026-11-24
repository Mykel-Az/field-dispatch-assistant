# ADR-025: A technician already on site is preferred for another job there

Date: 2026-11-24 · Status: Accepted

## Context
A dispatcher logged two jobs at the same address (an AC that will not cool and a
thermostat that is dead). The planner sent two technicians to one building. For a
customer that is two arrivals, two people at the door, and a technician who
cannot see the whole problem. For the company it is two drives to one place.
Under the Balanced strategy this happened because spreading work evenly can
outweigh a short drive.

## Decision
When ASSIGN scores the candidates for a job, a technician who **already has a job
that day and is within `SAME_SITE_MINUTES` (half a minute of driving) of this
one** is marked `same_site`. Among candidates who would not be late, `same_site`
ranks first; cost decides among the rest. The explanation says so ("Aisha
already has a job at this location.").

It is a preference, not a rule. It never beats:
- a skill the technician lacks, or their shift and closing time (FILTER),
- the daily limit (ADR-022): a technician at the limit is not chosen for a normal job,
- being on time: a technician who would be late ranks after one who would not
  (ADR-023), on site or not.

Being at the workstation with no jobs yet is not "on site"; the technician needs
at least one job already.

## Alternatives considered
- **Merge the jobs into one visit**: the right long-term model (one visit, shared
  setup time), but it changes the data model and the durations. Not now.
- **A cost bonus in the score**: depends on the weights; a bonus big enough to win
  sometimes would also win when it should not. A ranking step is predictable.
- **Customer or address matching in the engine**: the engine never sees the
  address (ADR-019). Distance is all it has, and distance is what "same place"
  means to the planner.

## Trade-offs
- TIME: "same place" is a travel-time threshold, so two flats in one building match
  but so do two shops a block apart. The full-fidelity path is a shared site id on
  the job (set by the dispatcher or from the geocoder's building).
- Both jobs need the skill. A technician who cannot do the second job is not chosen.
- A busy technician can collect several jobs at one site and leave others idle;
  the daily limit and lateness rules bound that.
