from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

# Caddy terminates TLS and proxies plain HTTP to gunicorn, setting this header on every
# request — without it Django can never tell a proxied HTTPS request from a plain HTTP one,
# and SECURE_SSL_REDIRECT / the *_COOKIE_SECURE flags below would misfire.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Start HSTS at a conservative 1 week rather than the usual 1-year max-age recommendation —
# raise it (and consider SECURE_HSTS_PRELOAD) only once the deployment has been confirmed
# stable over HTTPS, since a bad max-age is a one-way door for every visitor's browser.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 7)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
