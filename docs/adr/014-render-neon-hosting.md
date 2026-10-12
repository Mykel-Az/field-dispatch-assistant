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
