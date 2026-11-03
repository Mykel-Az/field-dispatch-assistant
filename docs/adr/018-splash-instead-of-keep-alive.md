# ADR-018: Cold-start splash screen instead of a keep-alive job

Date: 2026-11-03 · Status: Accepted

## Context
The backend runs on a free Render web service (ADR-014) that sleeps when it
is idle. The first request after a sleep is slow, and through the static
site's `/api` rewrite it can fail or time out. Without handling, a visitor
(a reviewer, a first customer) sees a blank page or a raw error and leaves.

## Decision
When the app loads, `WakeGate` asks `GET /api/health/` until the backend
answers, then shows the app.
- Each attempt is abandoned after 10 s and retried every 2 s.
- If the answer takes longer than 0.8 s, the app's logo appears and pulses
  slowly (no spinner, no card), large (96 px on phones, up to 160 px on desktop)
  on a soft teal background built from the design tokens. A warm backend never shows it.
- After 6 s a small, faded line under the logo explains that free hosting
  sleeps when idle. Before that, a short wait stays quiet instead of alarming
  the visitor. The reduced-motion setting turns the pulse off.
- After 90 s it stops and shows "We couldn't reach the server" with Try again.
- The probe uses no session, no CSRF and no 401 handling, so it cannot trigger
  a logout or a login redirect.

## Alternatives considered
- **Keep-alive cron job** (a ping every few minutes from a scheduler or an
  uptime service): the first visit is fast, but it adds a second service to
  run and watch, it hides the real behaviour of the hosting tier, and it
  spends the free instance hours that the plan limits. It also fails silently
  when the pinger stops.
- **Paid always-on instance**: removes the problem, but a recurring cost for a
  product with no revenue. This is the upgrade path once there are real users.
- **Do nothing**: the first impression for a reviewer is a blank page.

## Trade-offs
- The first visitor after a sleep still waits; they are told why.
- Only the initial load is covered. If the backend sleeps while a tab stays
  open, requests fail the normal way (map polling shows its "last updated"
  indicator and retries, per ADR-009).
- The "up to a minute" wording and the 90 s limit are our estimate, not a
  measured figure. TIME: record real cold-start times from the live site and
  adjust the text and limit.
