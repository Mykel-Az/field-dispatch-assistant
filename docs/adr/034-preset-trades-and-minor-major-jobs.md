# ADR-034: Preset trades as skills, and minor/major jobs

Date: 2026-11-28 · Status: Accepted · Builds on the category rules (CandidateSkillRule)

## Context
Three skills (HVAC, Electrical, Appliance Repair) were too few for a real field-service
business, and one skill per job category was too strict: a small electrical fix (change a
socket) can be done by a handyman or an appliance technician, while rewiring a panel must
be done by an electrician.

## Decision
- **Fifteen preset skills**, named like the trades a dispatcher recognises: Contractors &
  Handymen, Plumbers, Electricians, Heating & Air Conditioning, Appliances and Repair,
  Roofing, Locksmiths, Painters, Landscaping, Nurseries & Gardening, Florists, Tree
  Services, Home Cleaning, Furniture Stores, Movers. The three original skills were
  renamed in place, so existing technicians, jobs and rules keep working.
- **Fifteen job categories**, one per trade; each has exactly one *specialist* skill.
- **Each job is Minor or Major** (`Job.complexity`, default Major). A major job accepts
  the specialist only. A minor job also accepts the category's *helper* skills
  (`CandidateSkillRule.minor_only`).
- The planner is unchanged: it already matches a technician's skills against the job's
  acceptable skills. Minor/major only decides which skills are pre-selected when the job
  is created; the dispatcher can still tick any skills by hand.
- `GET /job-categories/` returns, for each category, the skill ids for a major and a
  minor job, so the form pre-selects from the server's rules instead of keeping its own
  copy (this removes the old name table in the frontend).

### Helper mapping (data, in migration 0014; edit it to change who may do a minor job)
| Category | Specialist | Also accepted for a minor job |
|---|---|---|
| Electricians | Electricians | Contractors & Handymen, Appliances and Repair |
| Heating & Air Conditioning, Appliances and Repair, Plumbers, Roofing, Locksmiths, Painters | itself | Contractors & Handymen |
| Landscaping | Landscaping | Nurseries & Gardening |
| Nurseries & Gardening, Tree Services | itself | Landscaping |
| Furniture Stores | itself | Movers |
| Contractors & Handymen, Florists, Home Cleaning, Movers | itself | none |

## Alternatives
- **One flat skill list, no minor/major.** Rejected: a handyman could never take a small
  electrical job, or an electrician would be wasted on a socket.
- **Skill levels (beginner, expert) per technician.** Rejected: more to maintain and to
  explain; the job-side rule gives the same result with one table.
- **Forms to create and edit skills.** Not built: skills and rules are global, so editing
  them would need a rule for who may change data every organization shares. **TIME.**
  Full fidelity: per-organization skills and a rules editor.

## Trade-offs
- The helper mapping is my default, not a trade standard; a business may disagree. It is
  data, so changing it needs no code.
- Several categories (Florists, Furniture Stores, Nurseries) are businesses more than
  skills; they are included as asked and behave like any other trade.
- Default durations per category are rough starting estimates (the existing TIME shortcut).
- Existing jobs become Major, the stricter reading, so no job suddenly accepts more people.
