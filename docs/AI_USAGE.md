# AI Usage Log

Per-section notes on AI-generated work: what the AI produced, what was changed or rejected
by review, and why. Consolidated into a final summary in Section 12.

## Section 1 — Monorepo, Docker (dev), settings

**What AI generated:** Django project skeleton (`backend/manage.py`,
`config/{settings/{base,dev,test,prod}.py,urls,celery,wsgi,asgi}.py`); six empty app packages
(`common`, `accounts`, `catalog`, `scheduling`, `bookings`, `notifications`) registered in
`INSTALLED_APPS`. `apps/common/exceptions.py`: `DomainError` base class plus
`custom_exception_handler` mapping `DomainError` and DRF's built-in exceptions
(`ValidationError`, `AuthenticationFailed`, `NotAuthenticated`, `PermissionDenied`, `NotFound`,
`MethodNotAllowed`, `Throttled`, `ParseError`) to the `{"error": {"code","message","details"}}`
envelope. `apps/common/views.py`: `HealthCheckView` (`GET /api/v1/health/`, `AllowAny`) pinging
Postgres (`SELECT 1`) and Redis (`PING`) independently, 200/503. `drf-spectacular` wired for
`/api/schema/` and `/api/docs/`. Tests: `test_health.py` (200 path, mocked-Redis-down 503 path),
`test_exceptions.py` (DomainError and DRF ValidationError envelope shape). Tooling:
`requirements/{base,dev,test,prod}.txt` (pinned), `pyproject.toml` (ruff + pytest config),
`conftest.py`, `.env.example`, multi-stage `Dockerfile` (non-root `app` user, `dev`/`prod`
targets), `.dockerignore`, root `docker-compose.yml` (db/redis/web/worker/beat, healthchecks,
YAML anchor sharing `DATABASE_URL`/`REDIS_URL`/Celery URLs across services pointed at Docker
service names), `Makefile`, `.editorconfig`. Key decisions: plain pinned requirements files over
Poetry/pyproject dependency groups; `psycopg[binary]` (psycopg3) over psycopg2; global
`IsAuthenticated` DRF default with explicit `AllowAny` on health/schema/docs; flat
(non-error-envelope) JSON shape for the health check response.

**What I changed / rejected:** No changes — reviewed the three flagged items (global
`IsAuthenticated` default, partial exception-handler test coverage, unverified
`docker-compose` build/run) and accepted all three as-is.

**Why:** `IsAuthenticated` stays as the global default for baseline security; public
endpoints (e.g. services/providers list in Section 3) will get explicit `AllowAny`
per-view as they're built, rather than defaulting the whole API open.
