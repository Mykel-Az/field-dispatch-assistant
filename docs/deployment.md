# Deployment checklist (Render + Neon)

What to set on Render, and how to prove it works. The app is one backend web
service plus one static site; the static site proxies `/api/*` to the backend
(ADR-014, ADR-015), so the browser only ever talks to the frontend origin.

## Backend web service

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Start command | `python manage.py migrate && python manage.py createcachetable && gunicorn config.wsgi` |
| Root directory | `backend` |

`DJANGO_SETTINGS_MODULE=config.settings.prod` selects the production settings.

| Environment variable | Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | a long random string (never the dev one) |
| `DATABASE_URL` | the Neon connection string |
| `ALLOWED_HOSTS` | `field-dispatch-assistant.onrender.com,field-dispatch-assistant-1.onrender.com` (the backend host, and the frontend host in case the rewrite forwards its Host header) |
| `CSRF_TRUSTED_ORIGINS` | `https://field-dispatch-assistant-1.onrender.com` (the **frontend** origin, with `https://`: that is the `Origin` the browser sends) |
| `CORS_ALLOWED_ORIGINS` | leave unset (same-origin through the rewrite, so CORS is not used) |
| `NUM_PROXIES` | `1` (confirm with the S1-1e spike) |
| `GEOCODER_CLASS` | `geocoding.nominatim.CachedNominatimGeocoder` |
| `NOMINATIM_USER_AGENT` | `FieldDispatch/1.0 (your-email)`, required by the Nominatim usage policy |
| `SECURE_SSL_REDIRECT` | unset (on). Set `false` only to switch the redirect off if it misbehaves |

## Check it after a deploy

```bash
API=https://field-dispatch-assistant-1.onrender.com/api   # through the frontend, like a browser

curl -si $API/health/ | head -1                           # 200
curl -si -c jar $API/auth/csrf/ | grep -i set-cookie      # csrftoken cookie arrives through the rewrite
TOKEN=$(grep csrftoken jar | awk '{print $7}')
curl -si -b jar -H "X-CSRFToken: $TOKEN" -H "Origin: https://field-dispatch-assistant-1.onrender.com" \
  -H "Content-Type: application/json" -d '{"email":"x","password":"y"}' $API/auth/login/ | head -1
#   400 or 401 = CSRF passed and the login was refused. 403 = CSRF_TRUSTED_ORIGINS is wrong.
curl -si http://field-dispatch-assistant.onrender.com/api/skills/ | head -3   # 301 to https
```

In the browser: sign in, reload (session survives), open the Map (tiles load,
pins appear), create a job (address is looked up).

Static files: `/api/docs/` (Swagger) and `/admin/` should be styled, not bare HTML.
That proves Whitenoise and `collectstatic` ran.

## Developer setup

```bash
pip install pre-commit && pre-commit install   # ruff check + format run before every commit
```

CI (`.github/workflows/ci.yml`) also runs `collectstatic` and `check --deploy`
against the production settings, so a broken deploy configuration fails the PR.
