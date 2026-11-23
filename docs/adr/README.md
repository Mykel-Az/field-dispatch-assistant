# Architecture Decision Records

One page per decision: context, decision, alternatives, trade-offs.
New decisions get the next number; superseded ADRs are marked, not deleted.

| # | Decision |
|---|----------|
| [001](001-django-drf-backend.md) | Django + DRF backend |
| [002](002-heuristic-over-optimal-solving.md) | Heuristic pipeline over optimal solving |
| [003](003-two-pass-sequencing.md) | Two-pass, slot-aware sequencing |
| [004](004-job-lifecycle-and-history.md) | Job lifecycle + append-only history |
| [005](005-no-live-gps-tracking.md) | No live GPS tracking |
| [006](006-haversine-distance-provider.md) | Haversine behind DistanceProvider |
| [007](007-nominatim-geocoding-with-fallbacks.md) | Nominatim geocoding with fallbacks |
| [008](008-service-layer-for-writes.md) | Service-layer writes |
| [009](009-polling-for-map-refresh.md) | Polling for map refresh |
| [010](010-week-ahead-slot-lookahead.md) | Week-ahead slot lookahead |
| [011](011-urgent-job-preemption.md) | Urgent-job preemption |
| [012](012-closing-time-feasibility-gate.md) | Closing-time feasibility gate |
| [013](013-vite-react-frontend.md) | Vite + React frontend |
| [014](014-render-neon-hosting.md) | Render + Neon hosting |
| [015](015-session-cookie-auth.md) | Session-cookie authentication |
| [016](016-multi-tenancy-explicit-scoping.md) | Multi-tenancy with explicit scoping |
| [017](017-roles-immutability-global-email.md) | Roles, immutability, global email |
| [018](018-splash-instead-of-keep-alive.md) | Cold-start splash instead of a keep-alive job |
| [019](019-engine-never-sees-customer-details.md) | The planning engine never sees customer details |
| [020](020-job-priority.md) | Job priority orders the work |
| [021](021-any-time-jobs.md) | "Any time that day" jobs are a movable window |
| [022](022-daily-limit-is-a-hard-cap.md) | The daily limit is a hard cap for planned work |
| [023](023-plan-in-deadline-order-and-never-late-by-choice.md) | Plan in deadline order; never choose a late technician when another is on time |
| [024](024-timezone-change-rule.md) | The time zone cannot change while jobs are Assigned or Ongoing |
