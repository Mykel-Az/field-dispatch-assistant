# Design and testing

## Architecture

### Dispatch engine: input and output types

The engine (`backend/dispatch_engine/`) is a pure module: standard library only,
enforced by `lint-imports`. It speaks only in the types in `types.py`; the
adapter in `api/adapters.py` turns Django models into these types and back.

| Type | Holds | Why |
|---|---|---|
| `Location` | lat, lng (validated range) | shared by jobs, technicians, the workstation, distance |
| `JobView` | id, label, location, urgency, created_at, slot (none only if urgent), duration, acceptable skill ids | what FILTER, SCORE and ASSIGN need about a job |
| `TechView` | id, label, skill ids, shift start and end, availability, `free_at`, `position`, assigned count | `free_at` and `position` let a second planning run account for jobs already assigned |
| `OrgConfig` | workstation, scoring strategy, speed, urgent buffer, at-risk threshold, daily job target | one place for the organization's planning settings |
| `Assignment`, `Unassigned`, `Plan` | the result: who got which job, who did not, and why | an unassigned job is an expected outcome, not an error |
| `Reason`, `Explanation` | reason codes with numbers; the sentence is built later | the structured reasons are the explanation of record |

Rules the types enforce, because a wrong plan is worse than a crash:
- All times are timezone-aware. The adapter converts organization-zone shifts to
  absolute times, so the closing-time gate (ADR-012) is a plain comparison.
- A non-urgent job must have a slot (invariant 7); a slot ends after it starts.
- Speed must be positive (distance divides by it); risk is between 0 and 1.
- Types are frozen, so inputs cannot change under the engine (invariant 14).
- No customer name, phone or address enters the engine.

### Clock and distance
- `Clock` (`SystemClock`, `FixedClock`) is injected, so the same input and a
  fixed time give the same plan. The engine reads it once per run.
- `DistanceProvider` (`HaversineProvider`) gives miles and travel minutes
  (ADR-006). Straight-line distance, times a road factor of 1.3 for travel time.


### Filter rules
For one job, each technician is checked in this order; the first failure is
the single reason recorded:
1. available;
2. shares at least one skill with the job (any-of, invariant 2);
3. estimated arrival no later than shift end (ADR-012), inclusive.

Estimated arrival is the latest of now, the technician's free time and shift
start, plus travel. For a job with a slot it is never earlier than the slot
opening. Results are in id order and do not depend on input order.

### Job order and priority
Planning runs in two passes (ADR-023). Pass 1 handles jobs urgent first, then
priority (high before low), then earliest deadline, then id; when there are not
enough places (the daily limit, shifts), the jobs that matter most get them.
Pass 2 plans only the jobs pass 1 placed, earliest deadline first, so a job with
a tight window is not pushed late by a high-priority job whose window is wide.
Pass 2 is used when it places every one of them and is no later overall. A
technician who would miss a job's window is chosen only when nobody can make it.
A job's window is fixed (agreed with the customer) or movable ("any time that
day", opening hours). Priority orders jobs; it is not used to pick the technician.
`PLANNER_LOG_LEVEL=DEBUG` or `manage.py plan_trace` shows each decision.

## Responsive layout (S2-9)
One rule: the app works at 360px wide first and gains room, it is not shrunk down
from a desktop layout.

- **Breakpoints.** Below 1024px (`lg`) staff see a top bar with a menu button; the
  navigation opens as a drawer. From 1024px up it is a sidebar. A technician has a
  single page, so they get a plain top bar and no menu at any size. One list of
  pages per role (`layout/navItems.ts`) feeds both, so they cannot differ.
- **Drawer.** Focus moves in and stays in (Tab wraps), Escape or a tap outside
  closes it, choosing a page closes it, the page behind does not scroll, and focus
  returns to the menu button. Component tests cover each of these.
- **Tables.** Technicians and Team use `StackedTable`: a table from 768px, a stack
  of cards below, each cell showing its column name. One markup, with explicit
  table roles so screen readers still read a table.
- **Everything else** (jobs list, filter bar, map, plan, forms) was already built as
  stacked, wrapping blocks and needed no change; the audit confirmed it.
- **Touch targets.** Buttons and inputs are at least 44px tall (`min-h-11`); the
  technician's three actions are 56px.

Manual check, 360 / 768 / 1280px, every page, signed in as head dispatcher
(horizontal overflow measured in the browser, then each page looked at):

| Defect found | Fixed? |
|---|---|
| Technicians table 329px wider than the screen at 360px | Yes: stacked cards |
| Team table 215px wider than the screen at 360px | Yes: stacked cards |
| Navigation tabs cut off ("Map" half hidden) in a scrolling row at 360px | Yes: menu button and drawer |
| Edit and Deactivate buttons touching on desktop after the change | Yes: spacing in the actions cell |
| Plan page: a job's title link is 20px tall (an inline text link) | Not fixed: the card around it is the larger target; noted for polish |
| Jobs list is one long scroll on a phone (about 50 cards) | Not fixed: paging or "load more" is a Sprint 3 candidate |
| Map status filters are 16px checkboxes | Not a defect: the whole chip around each is the tap target |
