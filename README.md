# Field Dispatch Assistant

A dispatch assistant for field-service teams (HVAC, electrical, appliance
repair). It plans a day's jobs across technicians, explains every assignment
in plain English, and re-plans when the day changes. Built as the MSSE
(Quantic) capstone.

## Links

| | |
|---|---|
| Live app | https://field-dispatch-assistant-1.onrender.com |
| API | https://field-dispatch-assistant.onrender.com/api/ |
| API docs (Swagger) | https://field-dispatch-assistant.onrender.com/api/docs/ |
| Task board (Trello) | https://trello.com/invite/b/6acb783d92c5f1520cd827ba/ATTI6905a380cde048f0dad94b121fe2295895AAFFA4/field-dispatch-assistant-msse-capstone |
| Design and testing document | [docs/design-and-testing.md](docs/design-and-testing.md) |
| Architecture decisions | [docs/adr/](docs/adr/README.md) |
| Demo recording | _TODO: add link_ |

> **Cold start:** the app is on free-tier hosting. After 15 minutes idle the
> backend sleeps and the first request can take about a minute. Open the live
> app once and wait for "API: ok" before using it.

## What it does

The engine runs four stages: **filter** (skills, hours, capacity) →
**score** (SLA risk, distance, workload) → **assign + sequence** (nearest
neighbour over real coordinates) → **replan** (technician unavailable, urgent
job, overrun). Each assignment comes with an explanation. A dispatcher map
shows job status and each technician's planned route.

Out of scope, by design: live GPS, live routing APIs, multi-day optimisation,
true optimal solving. See the ADRs for why.

## Tech stack

- **Backend:** Python, Django 6, Django REST Framework, drf-spectacular (OpenAPI)
- **Frontend:** React 19, TypeScript, Vite, react-router, Leaflet; API types
  generated with openapi-typescript
- **Database:** PostgreSQL (Neon in production; SQLite for local dev)
- **CI/CD:** GitHub Actions (ruff, import-linter, pytest on Postgres; eslint,
  vitest, build), auto-deploy to Render on merge to `main`

## Architecture

```
backend/
  dispatch_engine/   pure planning logic: stdlib only, no web or DB imports
  geocoding/         geocoder interface, Nominatim and fake implementations
  api/               Django/DRF: models, serializers, views, services, adapters
  config/            settings (base / local / test / prod), urls
frontend/            Vite + React app (dispatcher and technician views)
docs/adr/            architecture decision records
```

The dependency rule is enforced in CI with import-linter: `dispatch_engine`
imports nothing from `api`, `geocoding`, Django or DRF.

## Run locally

**Backend** (needs Python 3.12+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate        # also seeds the three starter skills
python manage.py runserver      # http://localhost:8000/api/health/
```

**Frontend** (needs Node 22)

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The frontend reads `VITE_API_BASE_URL` (default `http://localhost:8000/api`).

### Environment variables (backend, production)

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | Django secret key (required in prod) |
| `DATABASE_URL` | Postgres connection string (Neon) |
| `ALLOWED_HOSTS` | Comma-separated hostnames, no scheme |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins, with scheme |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, with scheme |

## Tests and quality checks

```bash
# backend
cd backend
ruff check . && ruff format --check .
lint-imports
pytest

# frontend
cd frontend
npm run lint && npm test && npm run build
```

Regenerate API types after changing the backend API:

```bash
cd backend && python manage.py spectacular --file schema.yml
cd ../frontend && npm run api:types
```

See the design and testing document for the full test strategy.

## Workflow

Work happens on short-lived branches and merges to `main` by pull request. The
`backend` and `frontend` CI checks must pass before merge. Progress is tracked
on the Trello board linked above.
