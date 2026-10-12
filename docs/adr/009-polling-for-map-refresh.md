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
