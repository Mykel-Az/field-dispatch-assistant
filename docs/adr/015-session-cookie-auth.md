# ADR-015: Django session-cookie authentication

Date: 2026-10-13 · Status: Accepted · Supersedes the auth part of ADR-001

## Context
Users are dispatchers and technicians of real companies. Access must be
revocable immediately (a fired technician, a compromised account), role and
organization must never be stale, and no credential should be readable by
page JavaScript (XSS). A token-based design (DRF token, JWT, access+refresh)
was considered first.

## Decision
Django session authentication (`SessionAuthentication`), HttpOnly + Secure +
SameSite=Lax cookie, DB-backed sessions.
- Revocation is immediate: `is_active=False` kills the session on the next
  request (ModelBackend.get_user rejects inactive users); a password change
  invalidates other sessions.
- The cookie is HttpOnly, so JS never holds a credential.
- Claims-free: role and organization are read from the database on each
  request, so changes and deactivation apply at once.
- It is Django's tested code, not custom token infrastructure.

## Prerequisites (each is part of the decision)
a. **First-party cookies.** The frontend calls the API same-origin: a Render
   static-site rewrite `/api/*` → backend in production, a Vite dev proxy
   locally. onrender.com is on the Public Suffix List, so cookies cannot be
   shared across the two Render hostnames. **Unverified:** Render's docs allow
   a full URL as a rewrite destination but do not document header/cookie
   behaviour. A time-boxed spike must prove `Set-Cookie` and `X-CSRFToken`
   pass through before any auth UI is built. Fallbacks: serve the built SPA
   from the Django service via WhiteNoise (one service, one origin), or a
   custom domain with a shared parent.
b. **CSRF.** `GET /api/auth/csrf/` sets the `csrftoken` cookie; the SPA sends
   `X-CSRFToken` on unsafe methods. DRF exempts views from CSRF and enforces
   it only for already-authenticated sessions, so login and register must be
   wrapped in `csrf_protect` explicitly, or login-CSRF is possible. Behind the
   proxy the browser's `Origin` is the frontend host, so
   `CSRF_TRUSTED_ORIGINS` must contain the frontend origin. CORS is then no
   longer needed in production.
c. **401, not 403.** `SessionAuthentication` has no `authenticate_header`, so
   DRF answers unauthenticated requests with 403. Use a subclass whose
   `authenticate_header` returns `"Session"` to get 401.
d. **Login throttling** (per IP and per email), counters in a DB-backed cache
   so they are shared across gunicorn workers.
e. **Scaling.** DB sessions are shared across instances, so they scale
   horizontally. The upgrade path is `cached_db` / Redis sessions plus a
   `clearsessions` job. TIME: no cleanup job now; expired rows accumulate
   slowly.
f. **Users with no organization (superuser)** are rejected by the API login
   and get 403 from every tenant endpoint. Superusers use Django admin only.

## Alternatives considered
- **DRF token**: no expiry, usually kept in localStorage (XSS-readable),
  revocation only by deleting the token.
- **JWT**: stale claims after role/org change or deactivation; real
  revocation needs a denylist, which is server state again.
- **Custom access + refresh tokens**: needs the same cookie + CSRF
  prerequisites plus roughly 3-4 days of custom security code.

## Trade-offs
- Requires same-origin deployment and CSRF handling (prerequisites above).
- Cookies fit browsers well; a native mobile app or third-party API
  consumers would not. **Revisit trigger:** either of those appears.
