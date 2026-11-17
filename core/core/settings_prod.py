"""Production settings (Render). Everything secret comes from environment variables."""
import os

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR, MIDDLEWARE

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
ALLOWED_HOSTS = [h for h in (_host, "localhost", "127.0.0.1") if h]
CSRF_TRUSTED_ORIGINS = [f"https://{_host}"] if _host else []

# Static files are served by WhiteNoise from STATIC_ROOT (filled by collectstatic at build time).
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Database: Postgres when DATABASE_URL is set (Neon), otherwise the SQLite file. The SQLite file lives on
# the instance's disk, which Render wipes on every deploy/restart, so real students need DATABASE_URL.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES["default"].get("HOST") not in ("localhost", "127.0.0.1", ""):
        # Hosted Postgres (Neon) is reached over the internet: never without TLS.
        DATABASES["default"].setdefault("OPTIONS", {}).setdefault("sslmode", "require")
    if "-pooler." in (DATABASES["default"].get("HOST") or ""):
        # Neon's pooled endpoint is PgBouncer in transaction mode: no server-side cursors there.
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Browsers remember to use HTTPS only (one year). Not for subdomains: onrender.com is shared.
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SILENCED_SYSTEM_CHECKS = [
    "security.W008",  # Render itself redirects every http:// request to https://.
    "security.W019",  # SAMEORIGIN on purpose: the Qo'llanma page shows its PDFs in an iframe.
]

# With DEBUG off Django prints no errors anywhere; send them to the Render log instead.
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
