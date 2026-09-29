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
