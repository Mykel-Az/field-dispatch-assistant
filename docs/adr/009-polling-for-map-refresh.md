# ADR-009: Polling (Tier 1) for map refresh

Date: <fill in> · Status: Accepted

## Context
The dispatcher map must reflect job and assignment changes without live
tracking. WebSockets/SSE add infrastructure that a free-tier host handles
poorly.

## Decision
Polling. The map refetches a thin payload (id, lat, lng, status,
technician_id) after the dispatcher's own actions, on tab focus, and on an
interval (5–10 s for the demo, configurable). Tier 1 = full thin refetch.

## Alternatives considered
- **SSE / WebSockets / webhooks**: lower latency, but more moving parts and
  idle connections on a spinning-down free host.
- **Tier 2** (`updated_at >= since`) and **Tier 3** (JobEvent log with cursor,
  `GET /events?since=<id>`): documented scale paths, not built. If Tier 3 is
  ever built, it must cover reassignment and resequencing events, not only
  status changes, or replans would be missed by the map.

## Trade-offs
- Wasted requests when nothing changed; fine at capstone scale.
- The client shows a "last updated" indicator and retries on failure
  (see failure-mode table).
- The append-only status history is core regardless of tier.

## Amendment (2026-11-19): the interval is 30 seconds
The "5–10 s for the demo" above was never what shipped; the app polls every
30 s (`POLL_INTERVAL_MS` in `usePolling.ts`), and this records why.

- **Own actions do not wait for it.** Assign, pin, edit and cancel call
  `notifyJobsChanged()`, so the dispatcher's own screens and other tabs of the
  same browser refresh at once. The interval only bounds how late *someone
  else's* change shows: a technician pressing Arrive or Complete, or a second
  dispatcher.
- **Those changes happen on a scale of minutes.** A job lasts an hour or more
  and technicians move between jobs in tens of minutes; a 30 s lag changes no
  decision a dispatcher makes from the map. At 5 s the page would send six
  times the requests for a view nobody can act on faster.
- **Cost.** One thin request every 30 s is two a minute per open tab. Every
  request also keeps the free-tier host and database awake (ADR-018), which is
  right while someone is looking at the map and wasteful when nobody is.
- **A hidden tab makes no requests.** The timer keeps ticking but skips while
  `document.visibilityState` is hidden. Coming back (tab shown or window
  focused; both events fire, so they are merged within 1 s) refreshes at once,
  so a returning dispatcher never waits up to 30 s for current data.

Raise or lower it in one place if the demo shows it is wrong. If a live
technician view is ever needed, that is the point to look at Tier 2/3 or SSE.
