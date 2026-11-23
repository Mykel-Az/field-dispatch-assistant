# Design and testing

How the system is built, why it is built that way, what it costs to run, and how
it is tested. Decisions are one page each in [`adr/`](adr/README.md); this
document gives the whole picture and links to them.

| Part | What it answers |
|---|---|
| [Architecture](#architecture) | What the pieces are and who may talk to whom |
| [The dispatch engine](#the-dispatch-engine) | Types, filter rules and job order in detail |
| [Patterns](#patterns-used-and-why) | Strategy, State, Adapter, service layer |
| [Tech choices](#tech-choices) | Each tool, the reason, the ADR |
| [Deployment and cost](#deployment-and-cost) | Where it runs, what else could run it |
| [Testing](#testing) | Levels, tools, what each protects, how to run |
| [Sprint 1 test inventory](#sprint-1-test-inventory) | What the suite held when Sprint 1 closed |
| [Responsive layout](#responsive-layout-s2-9) | How the UI adapts to a phone |

Status: Sprint 2 in progress. Sequencing (route order) and replanning are Sprint 3;
their engine files exist and are empty, and nothing below describes them as done.

## Architecture

### Overview
One backend, one single-page frontend, one database. The planner is a separate
pure module inside the backend so that the part that is hardest to get right is
also the part that is easiest to test.

```
 Browser (React SPA)                      Render static site
   dispatcher pages, technician page  ──► /api/* rewrite ──┐
                                                           ▼
                                           Django + DRF (gunicorn)
                                   views ► serializers ► services ► models ► Postgres (Neon)
                                                  │
                                       adapters.py│ (Django rows ⇄ engine types)
                                                  ▼
                                       dispatch_engine/  (pure Python)
                                                  
                                       geocoding/ ──► Nominatim (cached, 1 req/s)
```

A request for a plan: the view checks role and organization, the service
`generate_schedule` loads the day's jobs and technicians, the adapter turns them
into frozen engine types (no customer name, phone or address, ADR-019), the engine
returns a `Plan` with reasons, and the service writes assignments and history in one
transaction.

### Module boundaries
| Module | Owns | May import | May not import |
|---|---|---|---|
| `dispatch_engine/` | FILTER, SCORE, ASSIGN, lifecycle rules, explanations, clock and distance protocols | Python standard library | `api`, `geocoding`, `config`, `django`, `rest_framework` (CI fails the build) |
| `geocoding/` | `Geocoder` protocol, Nominatim client, cache, throttle, fake | standard library | the other three |
| `api/` | models, serializers, views, permissions, services, adapters | all of the above | n/a |
| `config/` | settings (base, local, test, prod), URLs | `api` | n/a |
| `frontend/src/` | pages, components, API client with types generated from `schema.yml` | n/a | the backend (it only talks HTTP) |

Inside `api/`, the direction is views → serializers (validate only) → services
(all business writes, ADR-008) → models. `adapters.py` is the only file that sees
both the models and the engine types. Every service takes `organization`
explicitly and filters by it (ADR-016), so one company never sees another's data.

The one rule that is enforced by a tool and not by discipline is the engine's
isolation: `lint-imports` runs in CI with a contract
"domain layer must not import infrastructure".

Frontend layout: `auth/` (session, guards), `dispatcher/` (jobs, map, plan, team,
organization), `technician/` (the one phone page), `layout/` (top bar, sidebar,
drawer), `shared/` (API client, polling, status and time helpers, UI class strings).

## The dispatch engine

### Input and output types

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

## Patterns used and why

| Pattern | Where | Why here, and what it buys |
|---|---|---|
| **Strategy** | `dispatch_engine/scoring.py`: `ScoringStrategy` protocol, `WeightedStrategy` with two weight sets (`nearest`, `balanced`), looked up by `Organization.scoring_strategy` | Companies differ on whether travel time or an even workload matters more. The choice is one setting; a third strategy is one entry and its tests. A guard test keeps the registry and the field's choices in step. `DistanceProvider` and `Clock` are the same idea: swappable behind a protocol (Haversine today, road distances later, ADR-006). |
| **State** (as a transition table) | `dispatch_engine/lifecycle.py`: `TRANSITIONS`, `TERMINAL`, `REASON_REQUIRED`, `IllegalTransition` | A job has seven statuses and the only behaviour that differs by status is "what may happen next, and is a reason required". That is data, not behaviour, so it is a table and not a class per state. It can be tested exhaustively (every pair of states), and the same table serves the dispatcher and technician endpoints (ADR-004). The database backs it with a partial unique index (one Ongoing job per technician) and an append-only history. |
| **Adapter** | `geocoding/`: `Geocoder` protocol with `NominatimGeocoder`, `FakeGeocoder`, `UnavailableGeocoder`; `CachingGeocoder` wraps any of them with the cache and the throttle. `api/adapters.py`: Django rows to engine types | The provider is an outside service with a rate limit and no SLA (ADR-007), so the app depends on a protocol and tests never touch the network. Settings pick the class (`GEOCODER_CLASS`). `api/adapters.py` is the seam that keeps Django out of the engine and customer data out of its logs (ADR-019). |
| **Service layer** | `api/services/` (`jobs`, `scheduling`, `accounts`, `locations`) | Assignment, status changes and replans must be atomic and race-safe (`transaction.atomic`, `select_for_update`). Putting that in views or serializers makes it hard to test and easy to bypass. Views stay thin, serializers only validate (ADR-008). |
| **Dependency injection of time** | `Clock`, `FixedClock` | Same input and a fixed time give the same plan, so planner tests are exact and property tests are possible. |

Not used, on purpose: no event bus or background worker (the plan runs in the
request at this scale, ADR-001), no repository layer over the ORM (services are
the boundary and Django's ORM is already one), no class-per-state State pattern
(see above).

## Tech choices

| Area | Choice | Reason in one line | ADR |
|---|---|---|---|
| Backend | Django 6 + Django REST Framework | ORM, migrations, auth and admin included; the data model is relational and constraint-heavy | [001](adr/001-django-drf-backend.md) |
| Database | PostgreSQL (Neon in production) | partial unique indexes and row locks are part of the design | [001](adr/001-django-drf-backend.md), [014](adr/014-render-neon-hosting.md) |
| Auth | Django session cookie (HttpOnly) | immediate revocation, no token readable by page scripts | [015](adr/015-session-cookie-auth.md) |
| Tenancy and roles | explicit organization scoping; head dispatcher, dispatcher, technician | one company never sees another's data | [016](adr/016-multi-tenancy-explicit-scoping.md), [017](adr/017-roles-immutability-global-email.md) |
| Planner | heuristic pipeline in a pure module | explainable and deterministic, unlike an optimal solver | [002](adr/002-heuristic-over-optimal-solving.md), [003](adr/003-two-pass-sequencing.md), [023](adr/023-plan-in-deadline-order-and-never-late-by-choice.md) |
| Job rules | lifecycle table with append-only history; priority; any-time jobs; hard daily limit; zone-change rule | each rule is a real dispatcher need, written down with its reason | [004](adr/004-job-lifecycle-and-history.md), [020](adr/020-job-priority.md), [021](adr/021-any-time-jobs.md), [022](adr/022-daily-limit-is-a-hard-cap.md), [024](adr/024-timezone-change-rule.md) |
| Distance | straight line times a road factor, behind `DistanceProvider` | no paid routing service, replaceable later | [006](adr/006-haversine-distance-provider.md) |
| Geocoding | OpenStreetMap Nominatim, cached and throttled, manual pin as fallback | free; failure is an expected outcome | [007](adr/007-nominatim-geocoding-with-fallbacks.md) |
| Live updates | polling every 30 s while the tab is visible; no GPS tracking | simple on a free host; changes happen over minutes | [009](adr/009-polling-for-map-refresh.md), [005](adr/005-no-live-gps-tracking.md) |
| Frontend | Vite + React 19 + TypeScript + react-router; Tailwind CSS v4; Leaflet for the map | client-rendered tool behind a login, no need for server rendering | [013](adr/013-vite-react-frontend.md) |
| API contract | drf-spectacular writes `schema.yml`; `openapi-typescript` turns it into frontend types | the frontend cannot call an endpoint that does not exist | [001](adr/001-django-drf-backend.md), [013](adr/013-vite-react-frontend.md) |
| Hosting | Render (web service and static site) + Neon | zero cost, a public URL, deploy on merge | [014](adr/014-render-neon-hosting.md), [018](adr/018-splash-instead-of-keep-alive.md) |
| Production server | gunicorn, WhiteNoise for static files | no extra web server to run | [deployment checklist](deployment.md) |
| Quality tools | ruff, import-linter, pytest + Hypothesis, vitest, ESLint, GitHub Actions | see [Testing](#testing) | [002](adr/002-heuristic-over-optimal-solving.md), [008](adr/008-service-layer-for-writes.md) |

## Deployment and cost

Today: a Render static site (the React build) rewrites `/api/*` to a Render web
service (Django + gunicorn), which talks to a Neon Postgres database. The browser
only ever sees one origin, so session cookies stay first-party (ADR-015). Settings
and the post-deploy checks are in the [deployment checklist](deployment.md).
GitHub Actions runs the same checks a deploy needs (migrations, `collectstatic`,
`check --deploy`) on every pull request.

Prices are not quoted here: they and the free-tier limits change, and ADR-014
says to re-verify them before final submission. The comparison is relative.

| Option | Running cost | What you get | What you give up |
|---|---|---|---|
| **Render free + Neon free** (used) | nothing | a public URL and automatic deploy on merge | the web service sleeps after 15 min idle (first request takes about a minute, handled by the splash screen, ADR-018); Neon scales to zero after 5 min; small storage and compute-hour allowance, short restore window and no long-term backups (ADR-014 figures, re-check) |
| **Paid Render instance + paid Neon tier** (recommended for real customers) | a recurring monthly bill per service | always on (no cold start, so no splash), more storage and compute, and backup and restore options that depend on the plan (check each provider) | money, with no revenue behind it yet; the app is unchanged |
| **Own VPS** (for example Contabo with Dokploy, considered in ADR-014) | one fixed monthly bill, typically low for the capacity | no sleeping, no expiry, full control | you own backups, patching, TLS and uptime; a single machine is a single point of failure; rejected for the added operational risk |
| **Render Postgres free** | nothing | one fewer vendor | expires 30 days after creation, before grading (ADR-014) |

Reading it: the free stack is right for a capstone and a demo. The first paid
step, always-on compute and a backed-up database, is the one to take when a real
company depends on the app; moving there is configuration (`DATABASE_URL`,
environment variables), not code. The VPS is the cheap-at-scale path for someone
willing to operate it.

What does not need paying for even later: the geocoder is cached and throttled to
fit Nominatim's public policy, and distance is computed locally. If volume
outgrows the public Nominatim instance, the options are a paid geocoder or a
self-hosted one, both behind the same `Geocoder` protocol (ADR-007).

## Testing

### Levels, tools, and what each protects

| Level | Tool | Where | What it protects | Needs |
|---|---|---|---|---|
| **Unit: pure engine** | pytest, Hypothesis | `dispatch_engine/tests/` (164 tests) | planning rules (filter, score, assign), types and their invariants, explanations, clock and distance. Property tests state rules such as "result does not depend on input order" and "a technician's jobs never overlap and arrive before closing" and let Hypothesis hunt for counterexamples | nothing: no database, no network |
| **Unit: parsing and helpers** | pytest | `api/tests/test_geocoding.py`, `test_adapters.py`, `test_geocoding_real_responses.py` | Nominatim parsing, cache, throttle, the Django-to-engine adapter. Real saved Nominatim responses guard against the provider changing its answers (ADR-007) | nothing |
| **Service and model** | pytest-django | `test_job_service`, `test_job_lifecycle`, `test_job_models`, `test_scheduling_service`, `test_models`, `test_timezone_rules` | business writes: every allowed and refused status move, history rows, atomicity, planning against the database, dates on the organization's clock | a database |
| **API** | DRF test client | `test_jobs_api`, `test_schedule_api`, `test_technician_jobs`, `test_technicians`, `test_users`, `test_auth`, `test_organization` ... | the HTTP contract: status codes, error codes, validation, who may call what | a database |
| **Security and isolation** | DRF test client | `test_permissions`, `test_tenant_isolation`, `test_https` | role checks and that one organization can never read or change another's data; HTTPS redirect | a database |
| **Concurrency** | pytest + threads | `test_job_edit_race`, `test_last_head_race`, `test_scheduling_race`, `test_technician_race` | two people acting at once: stale edits get 409, the last head dispatcher cannot be removed, two plans do not double-book, one Ongoing job per technician | **Postgres** (skipped on SQLite) |
| **Architecture and build gates** | import-linter, `makemigrations --check`, `check --deploy`, `collectstatic` | CI | the engine stays framework-free; no model change without a migration; production settings are deployable | nothing |
| **Static quality** | ruff (lint + format), TypeScript `tsc`, ESLint | CI (ruff also in pre-commit) | style, type errors, React hook mistakes | nothing |
| **Frontend** | vitest + jsdom, react-dom | `frontend/src/**/*.test.ts(x)` (174 tests) | the logic behind screens (models, filters, time formatting, API client errors) and component behaviour (forms, dialogs, drawer focus, polling, technician actions). No mocking library for the DOM; the API client is mocked | nothing |
| **Manual, in a real browser** | Playwright scripts run by hand | not in the repo's CI | each page at 360, 768 and 1280 px: overflow, tap targets, the real login and flows (results recorded in the responsive section) | a running app |

Why this shape: the engine is where wrong answers are most costly and where
tests are cheapest, so it has the most tests and no infrastructure. The database
levels exist because the rules that matter (one Ongoing job, tenant scoping,
locking) are enforced by the database and cannot be proved with mocks. Browser
checks stay manual for now: they found real defects (the responsive table) but
would add a slow, fragile CI job for a one-person project; automating a few
smoke flows is a Sprint 3 candidate.

### Running it
```bash
# backend (Postgres to include the race tests)
cd backend
ruff check . && ruff format --check . && lint-imports
python manage.py makemigrations --check --dry-run
DATABASE_URL=postgres://postgres:postgres@localhost:5432/dispatch pytest

# frontend
cd frontend
npm run lint && npm test && npm run build      # `npm run build` also type-checks

# after any API change
python manage.py spectacular --file schema.yml && (cd ../frontend && npm run api:types)
```
CI (`.github/workflows/ci.yml`) runs the same on every push and pull request,
backend against Postgres 16.

### Current size (collected, Sprint 2)
Backend 681 tests (including 8 that need Postgres or saved Nominatim responses),
frontend 174. Per-file counts: `pytest --collect-only -q`.

### Quality bar (as followed in Sprint 2)
- Every change ships with tests; a bug fix starts with a test that fails.
- A new test is proved meaningful by breaking the code it covers and watching it fail.
- An API change regenerates `schema.yml` and the frontend types in the same pull request.
- A UI change is tried in a real browser at phone and desktop width.

## Sprint 1 test inventory

Reconstructed by running the suite on the last Sprint 1 commit (`79aa508`, "fixed
ci secret key"), not copied from a CI log. CI runs the same files against
Postgres, where the two Postgres-only tests run instead of skipping. **348 backend
tests, 22 frontend tests, 0 failing.**

| File | Tests | Level | What it protects |
|---|---:|---|---|
| `test_jobs_api.py` | 96 | API | job create, list, edit, cancel, filters, validation, version conflicts |
| `test_job_lifecycle.py` | 52 | service | every allowed and refused status move; reasons required; history rows |
| `test_users.py` | 30 | API | team members, roles, deactivation rules |
| `test_technicians.py` | 25 | API | technician records, skills, availability |
| `test_job_models.py` | 23 | model | job constraints and defaults |
| `test_geocoding.py` | 21 | unit | Nominatim parsing, cache expiry and size, throttle, failures |
| `test_models.py` | 18 | model | model constraints (integrity rules) |
| `test_auth.py` | 16 | API | login, logout, CSRF, inactive users |
| `test_tenant_isolation.py` | 15 | security | other organizations' data is invisible and untouchable |
| `test_organization.py` | 14 | API | organization settings and optimistic locking |
| `test_job_service.py` | 13 | service | job writes under the service layer |
| `test_permissions.py` | 9 | security | role-by-endpoint matrix |
| `test_deactivate_jobs.py` | 9 | API | deactivating a technician: blocked while Ongoing, Assigned jobs released |
| `test_https.py` | 3 | security | HTTPS redirect, health check over plain HTTP, proxy header |
| `test_basic.py` | 2 | smoke | health endpoint, seeded skills |
| `test_job_edit_race.py` | 1 | concurrency (Postgres) | two edits with one version: one wins, one gets 409 |
| `test_last_head_race.py` | 1 | concurrency (Postgres) | two heads deactivating each other leave one |
| **Backend total** | **348** | | |
| `http.test.ts`, `jobTime.test.ts`, `status.test.ts`, `filters.test.ts` | 22 | frontend unit | API error handling, time formatting, status labels, list filters |

Between then and now the suite grew by 333 backend and 152 frontend tests: the
engine (164 tests, none at Sprint 1 close), planning service and API, technician
endpoints, priority, any-time jobs, time zone rules, and the plan, technician and
layout screens.

<!-- ## Gaps and known limits
- The planner is greedy: no gap insertion until Sprint 3 (`available_slots`);
  sequencing and replanning are Sprint 3.
- Frontend tests use jsdom, so layout, focus rings and real touch are checked by
  hand, not by CI.
- The time zone rule has a small race window (ADR-024).
- Real Nominatim responses are saved by a script run by hand; CI never calls it. -->

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

## AI tooling used in development

Added after the AI features are built (Sprint 3 stretch): what each tool is used for and how its output is verified.
