from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

# Full hardening (HSTS, CSRF_TRUSTED_ORIGINS, SECURE_PROXY_SSL_HEADER, static
# file serving) is Section 11's job. This file exists now only so the
# four-way settings split is complete and DJANGO_SETTINGS_MODULE=config.settings.prod
# is a valid, importable target.
