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

## Section 5 — Booking flow, state machine, idempotency

**What AI generated:** `apps/bookings/services/validation.py`: four pre-insert checks
(`not_on_grid`, `outside_booking_window`, `outside_working_hours`, `provider_on_time_off`), reusing
`_local_to_utc` from Section 4. `apps/bookings/services/booking.py`: `STATE_MACHINE` (a
`dict[(from,to), TransitionRule]` with per-edge actor and extra-rule checks) covering all four
edges from CLAUDE.md §6; `transition_booking` (`select_for_update` lock, state-machine lookup,
`is_late_cancellation` flagging, `BookingStatusLog` write, `transaction.on_commit` notification);
`submit_booking` (its own lock+log, since "submit without auto-confirm" isn't a status-changing
edge in the spec's table); `create_hold` (idempotency-key replay lookup; four validators;
auto-assign via `get_available_slots`'s returned `provider_ids` ordered by active-bookings-today
then id; per-candidate insert inside a nested `transaction.atomic()` savepoint; `IntegrityError`
constraint-name dispatch via `exc.__cause__.diag.constraint_name`, empirically verified against
the real DB); `expire_stale_holds` (iterates due holds through `transition_booking` individually,
so the "no transition may bypass transition_booking" rule holds even for the beat sweep).
Celery: `apps/bookings/tasks.py` + a plain `CELERY_BEAT_SCHEDULE` dict (60s) — no
`django-celery-beat` dependency added. `apps/notifications/services.py`: five no-op stubs for
Section 7. Six endpoints under `/api/v1/bookings/` (list/create, detail, submit, confirm, cancel,
complete), role-scoped via `get_queryset()` (customer/provider/admin) so out-of-scope ids 404
rather than 403. 54 new tests across 8 files, including three real-thread concurrency tests
(`threading.Barrier` + `connections.close_all()`, matching Section 2's established pattern):
10 customers racing one slot → exactly 1 success; auto-assign with 3 providers and 5 concurrent
requests → exactly 3 successes on 3 different providers; 5 concurrent requests with the same
`Idempotency-Key` → exactly 1 booking.

**What I changed / rejected:** The concurrency suite caught two real bugs during this session,
both fixed before considering the section done: (1) when a concurrent idempotency-key replay and
a provider/customer-overlap constraint were violated by the same insert, Postgres only reports one
constraint name, and the original code only checked for a replay when *that specific* constraint
fired — a losing thread got a raw 409 instead of the correct 200 replay. Fixed by checking for an
existing `(customer, idempotency_key)` match on *any* `IntegrityError` first, before interpreting
which constraint fired. (2) Ten threads racing an insert into the same exclusion-constrained range
intermittently deadlocked at the Postgres level (SQLSTATE `40P01`, `OperationalError`, not
`IntegrityError`) — uncaught, this surfaced as a raw 500 instead of a clean 409. Fixed by catching
`OperationalError` alongside `IntegrityError` in the retry loop and treating a confirmed deadlock
(`exc.__cause__.sqlstate == "40P01"`) the same as a lost conflict; any other `OperationalError` is
re-raised rather than silently swallowed.

**Why:** Both bugs were only found because the concurrency tests use real threads against real
Postgres rather than mocks (CLAUDE.md's own testing rule) — a mocked test would have exercised the
happy path of the retry loop and never hit either race. The deadlock in particular only reproduced
on some runs (a genuinely flaky failure — passed, then failed with 500s, then passed again across
three consecutive manual runs before the fix), which is exactly the "trust but verify" case for
concurrency-critical code: re-running a passing suite once is not enough evidence it's race-free.
After the fix, the three-test concurrency suite was run 3 times in a row (9 total passes, 0
failures) before considering it solid enough to hand off to Section 6's dedicated 20-run
stress-testing pass.

## Section 6 — Concurrency & edge-case hardening

**What AI generated:** `pytest-repeat` added to `requirements/test.txt` plus a
`make test-concurrency` target (`pytest apps/bookings/tests/test_concurrency.py --count=20`),
matching the spec's "for these tests only" scoping rather than repeating the whole suite. A
fourth concurrency test, `test_concurrent_confirm_and_cancel_same_booking_is_consistent`
(`test_concurrency.py`): a provider's `confirm_booking` and a customer's `cancel_booking` fired at
the same instant on the same pending booking via `threading.Barrier(2)`, asserting every logged
transition is a valid `STATE_MACHINE` edge and the persisted `booking.status` always matches the
last log row. `has_time_off_conflict`: a DB-level `Exists(TimeOff.objects.filter(provider=OuterRef
("provider"), start__lt=OuterRef("time_range__endswith"), end__gt=OuterRef
("time_range__startswith")))` annotation added once in `views.py::_scoped_queryset` (so list,
detail, and the transition endpoints all get it for free), exposed as a
`serializers.BooleanField(read_only=True, default=False)` on `BookingSerializer` — `default=False`
matters because `BookingDetailSerializer` also serializes bookings returned directly from service
functions (create/submit/confirm/cancel/complete), which were never built from the annotated
queryset and have no such attribute; DRF's `Field.get_attribute()` falls back to `default` on
`AttributeError` rather than raising. `test_business_deletion.py` (`catalog`): two new tests
proving `User.business`'s `on_delete=PROTECT` (set in Section 3) actually behaves as intended —
deleting a `Business` with staff raises `ProtectedError`, and deleting the staff first lets the
business delete succeed — a gap flagged during Section 6's code-race review as "verified manually
once, never automated." `test_edge_cases.py` (`bookings`): the four new edge cases from the spec —
time-off created over an already-`confirmed` booking flags `has_time_off_conflict` without
cancelling the booking; `price_snapshot`/`duration_snapshot` stay fixed after the underlying
`Service.price`/`duration_minutes` changes; deactivating a service leaves an existing booking fully
retrievable while rejecting a *new* hold against it with 404 `service_not_found`; changing
`User.timezone` never touches a booking's stored UTC `time_range`. `docs/EDGE_CASES.md`: one table
(`Edge case | How it's handled | Test`) compiling every edge case built across Sections 3-5 plus
this section's five, each row's test name checked against the actual suite (via a full
`grep '^def test_'` across `apps/`) before being written in, not recalled from memory.

**What I changed / rejected:** The new confirm/cancel concurrency test's first version was wrong,
not the code: it assumed exactly one of `confirm`/`cancel` must fail, and failed on the very first
run when both succeeded (`pending -> confirmed -> cancelled`). Tracing it through `STATE_MACHINE`
showed this is legitimate — `select_for_update()` correctly serializes the two calls, but
`(confirmed, cancelled)` is itself a valid edge (a customer may cancel an already-confirmed
booking), so a cancel that loses the initial race and re-reads a `confirmed` row is allowed to
succeed as a valid follow-on transition, not a bug. Rewrote the assertions to check what the
acceptance criterion actually means — no impossible transition ever logged, and `booking.status`
always matches the log — instead of forcing a stricter "exactly one must fail" shape that doesn't
hold. No production code changes were needed for this scenario: the code-race review's conclusion
(`transition_booking`'s existing `select_for_update()` already closes this race) held up under the
stress test.

**Why:** This is the one section where "no bug found" is itself the noteworthy result — Sections
2 and 5 each caught a real concurrency bug via a first-time real-thread test; Section 6's job was
to *prove*, not find, so a wrong test assumption failing on the first run needed to be diagnosed
carefully (read the state machine, don't just loosen the assertion) rather than reflexively treated
as another race bug to patch. The `has_time_off_conflict` `default=False` choice specifically
avoids a class of bug this session had already been burned by twice (Section 2's registration race,
Section 5's idempotency/deadlock races): trusting that every code path constructing a
`BookingDetailSerializer` goes through the annotated queryset would have caused a silent 500 on
every `create`/`submit`/`confirm`/`cancel`/`complete` response the moment the field was added, since
none of those return values come from `_scoped_queryset`. All 4 concurrency tests were run 20 times
each (`pytest --count=20`, 80 total runs) with zero failures before considering the acceptance
criterion met, and the full 188-test suite plus `ruff check`/`ruff format --check` were run clean
before finishing.
