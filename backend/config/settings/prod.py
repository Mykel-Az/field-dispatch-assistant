import dj_database_url

from .base import *

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {"default": dj_database_url.config(conn_max_age=600, ssl_require=True)}

STATIC_ROOT = BASE_DIR / "staticfiles"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])
# The SPA calls the API same-origin through Render's /api rewrite (ADR-015), so no
# other origin needs CORS in production. Set CORS_ALLOWED_ORIGINS only if that changes.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [])

# The app sends no email. Say so explicitly, so `check --deploy` stays quiet and a
# stray send fails loudly instead of printing to a log nobody reads.
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend"}}

# HTTPS. Render terminates TLS and forwards X-Forwarded-Proto (SECURE_PROXY_SSL_HEADER).
# Switch the redirect off with SECURE_SSL_REDIRECT=false in Render if it ever
# misbehaves, no redeploy needed. The health check stays reachable over plain http.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))  # raise once stable
# Deliberately not set: we do not own onrender.com, so telling browsers to force HTTPS
# on every subdomain, or to preload it, would be wrong. Silenced on purpose.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Throttle counters must be shared by every gunicorn worker, so use the database
# (run `python manage.py createcachetable` once per deploy(add to render start)). Redis is the upgrade.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_AGE = 14 * 3600

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
