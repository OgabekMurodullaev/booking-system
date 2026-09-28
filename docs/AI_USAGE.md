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

## Section 2 — Custom User, roles, JWT auth

**What AI generated:** `accounts.User(AbstractBaseUser, PermissionsMixin)` — email login,
`full_name`, `role` (`customer`/`provider`/`admin` via `TextChoices`), `timezone` validated
against `zoneinfo.available_timezones()` in `clean()`, DB-level case-insensitive uniqueness via
`UniqueConstraint(Lower("email"))`. `accounts/managers.py`: `UserManager` with `create_user`/
`create_superuser` (email normalization/lowercasing, `full_clean(exclude=["password"])`,
role/staff/superuser defaults per method). Project's first migration
(`accounts/migrations/0001_initial.py`) with `AUTH_USER_MODEL` set before it. JWT via
`djangorestframework-simplejwt`: `SIMPLE_JWT` settings (15 min access / 7 day refresh, rotation +
blacklist), `rest_framework_simplejwt.token_blacklist` added to `INSTALLED_APPS`. Endpoints under
`/api/v1/auth/`: `RegisterView` (`CreateAPIView`, forces `role=customer` server-side, `role` is a
read-only serializer field so it can't be set via input), `LoginView` (subclassed
`TokenObtainPairView` with `EmailTokenObtainPairSerializer` adding a `user` payload to the
response), `RefreshView` (plain `TokenRefreshView`), `LogoutView` (`IsAuthenticated`, blacklists
the given refresh token via `RefreshToken(...).blacklist()`, 205 on success), `MeView`
(`RetrieveUpdateAPIView`, `email`/`role` read-only so PATCH/PUT can't change them). Scoped
throttling (10/min) on register/login via `ScopedRateThrottle`. `apps/common/permissions.py`:
`IsCustomer`, `IsProvider`, `IsBusinessAdmin` (role checks on `request.user`). `UserAdmin`
registration reusing Django's `UserAdmin` base. 22 new tests across
`test_models.py`/`test_registration.py`/`test_auth_flow.py`/`test_permissions.py`/`test_admin.py`,
plus a new `conftest.py` autouse fixture (`cache.clear()`) added to stop DRF throttle state from
leaking between tests. Key decisions: timezone/role format validation done in the
model/serializer (input-shape validation), not a service; the actual account-creation step goes
through a one-line `apps/accounts/services/registration.py::register_customer()` to keep the
"fat services" pattern consistent; `logout` requires authentication (deviates from simplejwt's
stock `AllowAny` `TokenBlacklistView`); `register` does not auto-login (returns profile only, no
tokens); `config/settings/test.py` `CACHES` switched to `LocMemCache` for test isolation.

**What I changed / rejected:** Reviewed and fixed two real gaps caught by manual review, not
accepted as generated: (1) `apps/accounts/services/registration.py::register_customer()` now
catches `IntegrityError` and raises a `DomainError` (`validation_error`, same shape as the normal
duplicate-email response) instead of leaking a raw 500 when two concurrent registrations race past
the serializer's `.exists()` check. (2) `RegisterSerializer.validate_password()` now builds an
unsaved `User(email=..., full_name=...)` and passes it to `validate_password(value, user=...)` —
previously called without `user=`, which silently disabled `UserAttributeSimilarityValidator`
(Django's own guard is `if not user: return`), so a password identical to the submitted email/full
name was accepted. Added `test_concurrent_duplicate_registration_only_one_succeeds` (real threads,
`transaction=True`, per CLAUDE.md's concurrency-testing rule) and
`test_register_password_similar_to_email_rejected` to prove both fixes.

**Why:** The concurrency gap was found by asking "what does a sequential duplicate-email curl
test actually prove?" — it doesn't cover two simultaneous requests, which is the scenario the
DB-level `UniqueConstraint` exists to guard against per architecture rule 3 ("DB is the last line
of defence"); the view/service needs to translate that constraint's failure into the same clean
error shape, not just rely on the constraint existing. The password-similarity gap was found by
tracing exactly what `validate_password(value)` without `user=` does in Django's source rather
than assuming the default validator list "just works" — worth catching before Section 6 explicitly
audits concurrency and edge cases, since this one was cheap to fix immediately instead of carrying
it forward as debt.

## Section 3 — Core models, DB constraints, admin

**What AI generated:** All remaining domain models: `catalog.Business/Service/Provider`,
`scheduling.WorkingHours/TimeOff`, `bookings.Booking/BookingStatusLog`, plus `accounts.User.business`.
DB invariants per CLAUDE.md §5: `Service` duration (5-480, step-of-5 via a `RawSQL` check since
Django has no `%`-remainder lookup) and buffer (0-120) check constraints; `WorkingHours`/`TimeOff`
start-before-end checks; `Booking`'s two `ExclusionConstraint`s (provider/`blocked_range` and
customer/`time_range` overlap, both GiST via `BtreeGistExtension()` as the first migration
operation), the idempotency-key `UniqueConstraint`, and the `pending⇔expires_at` check; `(provider,
status)`/`(customer, created_at)` indexes. Added a DB check constraint requiring `business` for
`role in (provider, admin)` (superusers exempted — they're a site-admin concept, not a
business-scoped role). Admin-facing CRUD: `services/`, `providers/` (creates the `User` + `Provider`
together via `apps.catalog.services.providers.create_provider`, validating assigned services belong
to the same business), `providers/<id>/working-hours/` (public GET, admin-or-self replace-all PUT),
`providers/<id>/time-off/` (full CRUD, admin-or-self only) — all via `apps/catalog/permissions.py`'s
`IsBusinessAdminOrOwnProvider`. Soft-delete on `Service`/`Provider` (`is_active=False`, row kept).
84 tests across `catalog`/`scheduling`/`bookings`, plus a shared `apps/conftest.py` (business,
admin, provider, customer fixtures + an `auth_client()` helper) to cut duplication across the three
apps' test suites. Key decisions: WorkingHours overlap enforced in a service function
(`validate_no_overlap`) + tests rather than a DB exclusion constraint, since Postgres has no
built-in range type for bare `time` and the invariant is only ever broken by a single admin/provider
action, never a concurrent race (unlike `Booking`, which stays DB-enforced); public `services/`/
`providers/` listings and detail views are unscoped across businesses for *active* rows (public
data), with cross-business isolation applying to inactive rows and all write operations;
`User.business`'s `on_delete` set to `PROTECT` (not `SET_NULL`) after a manual test showed
`SET_NULL` lets deleting a `Business` silently orphan its staff into an invalid constraint state;
`CheckConstraint.check` renamed to `.condition` project-wide to clear a Django 5.1
deprecation warning ahead of Django 6.

**What I changed / rejected:** No changes on review — the three flagged decisions (active
services/providers publicly visible across businesses while inactive rows and writes stay
isolated; `working-hours/` GET public but `time-off/` admin-or-self only; `User.business`
`on_delete=PROTECT`) were accepted as-is. The `on_delete=PROTECT` fix, the
`CheckConstraint.check`→`.condition` rename, and the Section 2 `test_permissions.py` regression
fix were already caught and corrected during implementation (via manual ORM testing and the full
test run), not separate changes requested afterward.

**Why:** Active services/providers being cross-business-visible matches how public data should
behave (same as an anonymous visitor sees) — isolation is about the admin's own management
surface, not about hiding public listings. The working-hours/time-off asymmetry follows the
spec's own wording (working hours are storefront-like info; time off can carry a private reason).
`PROTECT` was chosen over `SET_NULL` specifically because testing surfaced that `SET_NULL` lets a
`Business` delete silently orphan its own staff into a constraint-violating state — `PROTECT`
forces that to be handled explicitly instead of failing implicitly.

## Section 4 — Availability engine

**What AI generated:** `apps/scheduling/services/intervals.py`: pure `merge_intervals`/
`subtract_intervals` (half-open `[start, end)` tuples, zero Django/DB imports). `apps/scheduling/
services/availability.py`: `Slot` dataclass; `_local_to_utc` (DST-safe local-wall-clock→UTC
conversion via `zoneinfo`, detecting spring-forward gaps by round-tripping the conversion and
comparing, using `fold` for fall-back ambiguity); `_grid_starts` (15-min local-time-of-day grid
within a working-hours interval); `_group_slots_by_time` (the spec's "merge across providers" —
deliberately named/kept separate from `merge_intervals`, since it groups already-computed slots by
identical start/end rather than doing interval algebra); `get_available_slots(service, date_from,
date_to, provider, now)` — 4 fixed DB queries total regardless of day-range or provider count
(candidate providers, `WorkingHours`, `TimeOff` in the UTC window, active bookings via
`Q(status=confirmed) | Q(status=pending, expires_at__gt=now)` pushed into the DB filter so an
"expired pending" — status still literally `pending` since no expiry sweep exists until
Section 5/6 — correctly stops blocking); `find_alternatives(service, around, provider, limit, now)`
— forward-only, windowed, reuses `get_available_slots`. Endpoint `GET /api/v1/availability/`
(`AllowAny`): `AvailabilityQuerySerializer` (date/range shape only), service/provider existence+
active resolution done in the view (matching `ServiceDetailView`'s precedent), response grouped by
local business-timezone date including empty dates. 43 new tests: `test_intervals.py` (pure,
16 cases), `test_availability_service.py` (13 cases incl. two `Europe/Berlin` DST-transition tests
that self-verify via round-tripping through `_local_to_utc` rather than hand-computed magic
numbers), `test_availability_api.py` (10 cases incl. a `CaptureQueriesContext`-based test proving
the query count is identical for a 1-day and a 14-day/2-vs-3-provider request), `test_find_
alternatives.py` (4 cases). Key decisions: DST gap → drop the interval for that date rather than
clamp; DST fold → always `fold=0` (earlier occurrence); `now` is a required/optional parameter
threaded through every function, never `timezone.now()` inside the deterministic core (only the
view and `find_alternatives`' outer default call it, exactly once each).

**What I changed / rejected:** No changes on review — the three flagged decisions (DST gap-drop
and fold=0 policy; the unpinned "grouped by date" response schema; the query-count test asserting
"identical count, ≤10" rather than an exact fixed number) were accepted as-is.

**Why:** The DST policy is a judgment call with no acceptance criterion dictating the alternative,
and the target region (Central Asia, per the business's default `Asia/Tashkent` timezone) doesn't
observe DST at all — this only matters if the system is later used by a business in a DST-observing
timezone, at which point dropping ambiguous/nonexistent boundary times is the safer default over
silently clamping. The response schema was left as proposed since nothing downstream (Section 9's
frontend) exists yet to validate it against — it can still be adjusted then without churn elsewhere,
since only this endpoint produces the shape. The query-count test's looser assertion ("same count
for 1 day vs 14 days, same count for 2 vs 3 providers, bounded by 10") was kept because it proves
the actual acceptance criterion — the count doesn't grow with range/provider count — without
hard-coding a magic number that would need updating every time an unrelated query is added
elsewhere in the request cycle (e.g. auth middleware), which would make the test brittle for the
wrong reason.
