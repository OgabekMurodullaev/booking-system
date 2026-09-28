from .base import *  # noqa: F403
from .base import env

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["*"]

_test_database_url = env("TEST_DATABASE_URL", default="")
if _test_database_url:
    DATABASES["default"] = env.db_url_config(_test_database_url)  # noqa: F405

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttle state lives in the cache backend; use a per-process cache in tests so
# DRF throttle counters never leak between test runs via the real Redis instance.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
