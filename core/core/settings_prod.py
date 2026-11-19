"""Production settings for a deployment behind a trusted HTTPS proxy."""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR, MEDIA_ROOT, MIDDLEWARE, PRIVATE_MEDIA_ROOT

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

def _env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
_render_hosts = [_render_host] if _render_host else []
ALLOWED_HOSTS = list(dict.fromkeys([
    *_env_list("DJANGO_ALLOWED_HOSTS"), *_render_hosts, "localhost", "127.0.0.1",
]))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([
    *_env_list("DJANGO_CSRF_TRUSTED_ORIGINS"), *(f"https://{host}" for host in _render_hosts),
]))

# Static files are served by WhiteNoise from STATIC_ROOT (filled by collectstatic at build time).
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_ROOT = os.path.realpath(os.environ.get("AVTO_MEDIA_ROOT") or MEDIA_ROOT)
PRIVATE_MEDIA_ROOT = os.path.realpath(os.environ.get("AVTO_PRIVATE_MEDIA_ROOT") or PRIVATE_MEDIA_ROOT)
if os.path.commonpath([MEDIA_ROOT, PRIVATE_MEDIA_ROOT]) == MEDIA_ROOT:
    raise ImproperlyConfigured("Private uploads must be stored outside the public media directory.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not bool(_render_host)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Production installations use PostgreSQL through DATABASE_URL.
# SQLite remains available for legacy preview deployments.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES["default"].get("HOST") not in ("localhost", "127.0.0.1", ""):
        # Hosted PostgreSQL is reached over the internet. Require TLS unless the URL specifies a mode.
        DATABASES["default"].setdefault("OPTIONS", {}).setdefault("sslmode", "require")
    if "-pooler." in (DATABASES["default"].get("HOST") or ""):
        # Neon's pooled endpoint is PgBouncer in transaction mode: no server-side cursors there.
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Apply HSTS to the configured host.
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SILENCED_SYSTEM_CHECKS = [
    "security.W019",  # SAMEORIGIN on purpose: the Qo'llanma page shows its PDFs in an iframe.
]
if _render_host:
    SILENCED_SYSTEM_CHECKS.append("security.W008")  # Render redirects HTTP at the edge.

# Write production errors to the service supervisor's log.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{levelname} {asctime} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "avto": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
