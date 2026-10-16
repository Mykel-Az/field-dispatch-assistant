# ADR-014: Render (compute) + Neon (Postgres) hosting

Date: 2026-10-10 · Status: Accepted

## Context
Needs: a public deployed URL through grading, real Postgres (partial indexes,
row locking), auto-deploy on merge to main, zero cost.

## Decision
- Backend: Render free web service (Django + gunicorn). Migrations run in the
  start command because the free tier has no shell.
- Frontend: Render static site.
- Database: Neon free Postgres via `DATABASE_URL`.

## Alternatives considered
- **Render Postgres (free)**: expires 30 days after creation, before grading.
- **Railway**: one-time trial credit, then paid.
- **Own VPS (Contabo + Dokploy)**: no expiry or cold start, but I own backups,
  patching and uptime. Rejected for added operational risk.

## Trade-offs
- Render free web services sleep after 15 minutes idle; the first request
  takes about a minute. Mitigation: wake the site before demo or grading; the
  README says so; the frontend shows a loading state.
- Neon scales to zero after 5 minutes (short delay on first query).
- Neon free: 1 GB storage, 100 compute-hours/month, 6-hour restore window, no
  long-term backups. Seed data is reproducible from migrations.
- Provider limits change; re-verify before final submission.
- Cost note for the design document: free for the capstone; a paid Render
  instance plus a paid Neon tier would be the production recommendation.


> **Amendment 2026-10-13:** Production serves the API same-origin through a
> Render static-site rewrite `/api/*` → backend (ADR-015 prerequisite a), with
> `CSRF_TRUSTED_ORIGINS` set to the frontend origin; CORS is no longer used in
> production. A deploy smoke test must call `/api/health/` through the
> frontend origin and assert a JSON response (a missing rewrite returns
> `index.html` with status 200). Fallback if the rewrite does not pass cookies:
> serve the SPA from the Django service via WhiteNoise. The Neon schema is
> reset once when `AUTH_USER_MODEL` changes (migrations regenerated).