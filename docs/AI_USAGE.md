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

## Section 7 — Notifications (Celery, email, .ics)

**What AI generated:** `apps/notifications/tasks.py`: four Celery tasks
(`send_booking_confirmed`, `send_booking_cancelled`, `send_booking_pending_approval`,
`send_booking_reminder`), each `@shared_task(bind=True, autoretry_for=(Exception,),
retry_backoff=True, max_retries=5)`, sharing one `_send()` helper that renders a
plain-text + HTML template pair, formats `booking.time_range` in the *recipient's own*
`User.timezone` via `zoneinfo`, and sends through `EmailMultiAlternatives`; plus
`scan_and_send_reminders_task`, a beat task (every 15 min, `CELERY_BEAT_SCHEDULE`) that finds
confirmed bookings starting in the `[now+24h, now+24h+15min)` window with `reminder_sent_at`
still null, atomically claims each one via a single `.filter(...).update(reminder_sent_at=now)`
(rowcount tells you whether *you* won the claim) before enqueuing, so two overlapping scans can
never double-send. `apps/notifications/ics.py`: `build_ics(booking, method)` using the new
`icalendar` dependency — stable `UID` (`booking-{id}@bookingsystem`), `METHOD:REQUEST` or
`METHOD:CANCEL`. Wired the four real bodies into the existing `apps/notifications/services.py`
no-op stubs (`notify_hold_created`/`notify_booking_completed` stay no-ops — not in the spec's
task list). New `Booking.reminder_sent_at` field + migration. New endpoint
`GET /api/v1/bookings/{id}/calendar.ics` (`BookingCalendarView`), scoped through the same
`_scoped_queryset()` every other booking endpoint uses, so only whoever can already see the
booking can download its `.ics`. `EMAIL_BACKEND`/SMTP/`DEFAULT_FROM_EMAIL` settings added to
`base.py` (console backend by default, env-overridable), `.env.example` updated to match. 8 new
tests across `test_tasks.py` and `test_calendar_endpoint.py`: correct recipient per task
(provider for pending-approval, customer for the rest), timezone-correct rendering (asserted by
setting a non-UTC `User.timezone` and checking the rendered local time, not the raw UTC one), the
`.ics` attachment round-trips through `icalendar.Calendar.from_ical()` with the right `UID`/
`METHOD`, the reminder scan run twice only sends once, a booking outside the reminder window is
left alone, a rolled-back transition leaves `mail.outbox` empty, and the calendar download 404s
for a user who isn't the booking's customer/provider/admin.

**What I changed / rejected:** No changes on review — the two flagged decisions (attaching a
cancellation `.ics` in addition to the confirmation one; using `retry_backoff` on all four tasks
rather than only the ones the spec called "idempotent") were accepted as-is. One test-design fix
made during implementation, not a code bug: my first versions of the confirm/cancel/pending-
approval tests used plain `@pytest.mark.django_db`, and all three failed with an empty
`mail.outbox` — not because the email code was wrong, but because Django wraps a plain
`django_db`-marked test in an atomic block that's rolled back (never committed) at teardown, so
`transaction.on_commit()` callbacks registered during the test never fire at all. Switched those
three tests to `@pytest.mark.django_db(transaction=True)`, matching the pattern the concurrency
tests already established in Section 2/5/6 for the same reason.

**Why:** The `on_commit`-vs-plain-`django_db` gotcha is exactly the kind of thing that would have
silently produced "0 emails sent, test happens to pass because I forgot to assert on it" if
caught less carefully — here it failed loudly instead, because the test asserted the outbox
directly, which is the whole point of testing "notifications are only sent after commit" as its
own acceptance criterion rather than assuming the `transaction.on_commit` wiring from Section 5
"just works" under test. Attaching the cancellation `.ics` (not just the confirmation one) follows
the spec's own wording literally ("a cancellation sends a METHOD:CANCEL with the same UID") rather
than reading it as prose-only description of what a *real* calendar client would receive out of
band — since this project has no separate calendar-sync service, the cancellation email is the
only place that `METHOD:CANCEL` message can come from.

## Section 8 — Frontend foundation: setup, auth, API client

**What AI generated:** `frontend/` scaffolded via Vite (React 19 + TypeScript), then wired with
Tailwind v4, shadcn/ui (`components.json`, "new-york" style), TanStack Query, React Router,
react-hook-form + zod, date-fns/date-fns-tz, ESLint (flat config, typescript-eslint,
react-hooks/react-refresh plugins) + Prettier — replacing the scaffold's default `oxlint` to match
CLAUDE.md's explicit "ESLint + Prettier" stack choice. `src/index.css` carries `DESIGN.md`'s exact
color/typography tokens as Tailwind v4 CSS variables (`:root`/`.dark`), mapped once via `@theme
inline` so Tailwind utility classes (`bg-primary`, `text-accent-text`, etc.) resolve to them.
`src/api/`: `client.ts` (a single `openapi-fetch` instance + middleware attaching
`Authorization: Bearer <token>` per request and handling a 401 with a single-flight refresh —
concurrent 401s all await one shared `Promise`, and the original request is cloned *before* it's
sent so its one-shot body stream can be replayed after the token refreshes), `tokens.ts` (access
token in a module-level variable, never persisted; refresh token in `localStorage`), `errors.ts`
(`ApiError` + `unwrap()`, normalizing every non-2xx response into the backend's
`{code, message, details}` envelope). `src/auth/`: `AuthContext` (boot-time silent refresh so a
page reload doesn't look logged out, `login`/`logout`), `RequireRole` (a route-guard layout route:
redirects to `/login` if unauthenticated, to the user's own role-home if authenticated but wrong
role). Routes: `/login`, `/register` (both react-hook-form + zod, demo-account buttons on Login
gated on `VITE_DEMO_*` env pairs), `/`, `/provider`, `/admin` (each behind `RequireRole`, sharing
one `Layout` — header with user-menu dropdown and a timezone indicator). `frontend/Dockerfile`
(multi-stage Node build → nginx with an SPA `try_files` fallback) + `nginx.conf`.
`npm run gen:api` (`openapi-typescript` against the live dev backend) generates `src/api/
schema.d.ts` — never hand-edited, per the section's own acceptance criterion.

**What I changed / rejected:** Two real backend schema-accuracy gaps were found and fixed while
building the typed client — not frontend workarounds, since CLAUDE.md requires the generated
types to actually be correct: (1) `LoginView`'s documented response reused
`EmailTokenObtainPairSerializer`'s *input* fields (`{email, password}`) because
`TokenObtainPairSerializer.validate()` injects `access`/`refresh`/`user` onto the response dict at
runtime, outside its declared `fields` — invisible to drf-spectacular's static introspection.
Fixed with a `LoginResponseSerializer` + `@extend_schema_view(post=extend_schema(responses=...))`
on `LoginView` (`apps/accounts/serializers.py`, `apps/accounts/views.py`). (2) Every serializer's
read-only fields (e.g. `Register.id`/`.role`) showed up as *required* in the generated request
body type, because request and response shared one undifferentiated schema — `tsc` correctly
refused to compile a register call missing server-assigned fields it should never send. Fixed by
turning on `COMPONENT_SPLIT_REQUEST` in `SPECTACULAR_SETTINGS` (`config/settings/base.py`), which
made drf-spectacular emit proper `XRequest` variants project-wide (verified: full 196-test backend
suite still green after both changes). Beyond that, no changes on review — the plan's other
decisions (in-memory access token / localStorage refresh token, single-flight refresh, `sonner`
for unexpected errors only, timezone indicator showing the signed-in user's own `timezone` rather
than a separate business-timezone field that `/me/` doesn't expose) were accepted as-is.

**Why:** Both schema fixes are the same category of bug as the frontend's own explicit `ApiError`
design: trusting a serializer's declared `fields` to describe its *actual* runtime behavior is
exactly the assumption that silently breaks the moment a view does something dynamic (injecting
extra response keys, or accepting write-only fields disjoint from its read shape) — and Section
8's own acceptance criterion ("no hand-written API response types") only means something if the
generated types are actually trustworthy enough to build against without a manual override. Both
were caught by `tsc` itself refusing to compile, not by inspection — the same "let the compiler
find the gap" discipline this project's test suite has relied on since Section 2's concurrency
tests. Every flow (register → login → role redirect → reload-persists-session → wrong-role
redirect → logout, for all three roles) was verified against the real dev backend and real
Postgres via the browser tool, not a mock; the 401-triggers-refresh-and-retry path was verified by
code review rather than a live run, since forcing a real 401 needs either a 15-minute wait for the
access token to expire or a temporary settings change neither of which seemed worth the time
against a stress-tested, single-flight-guarded implementation — flagged here rather than silently
assumed correct.

## Section 9 — Frontend: customer booking flow

**What AI generated:** A real drf-spectacular bug found while planning this section, fixed before
writing any frontend code: `POST /api/v1/bookings/` documented its 201 response as the
*create-input* shape (`{service, provider, start}`) instead of the actual `BookingDetailSerializer`
response the view returns, because `extend_schema` decorating `BookingListCreateView.create()`
directly was silently ignored by drf-spectacular for this specific generic-view mixin action —
switching to `@extend_schema_view(post=extend_schema(...))` (keying by the dispatched HTTP handler
name rather than the DRF mixin action name) fixed it; empirically verified via a debug
`operation_id` marker before settling on the real fix. A second small backend addition:
`would_be_late_cancellation` (`apps/bookings/serializers.py`), a computed field mirroring
`transition_booking`'s own late-cancellation check, so the frontend can warn *before* a customer
confirms a cancellation rather than only reporting it after the fact — no `/businesses/` endpoint
exists to expose `cancellation_window_hours` directly, and duplicating that timezone-sensitive
calculation in JS would have been a second, divergeable copy of business logic. Frontend: a
provider selector that derives its options from the union of `provider_ids` across one unfiltered
14-day availability fetch (no `?service=`-filtered providers endpoint exists — confirmed by reading
the live schema, not assumed), so switching providers is a pure client-side re-filter of already-
fetched data, never a second network round-trip; a 14-day date strip and a slot grid grouped
morning/afternoon/evening in the business's own timezone with a live "Asia/Tashkent time" label;
hold creation with a fresh `Idempotency-Key` per slot click and a derived (not effect-synced)
10-minute countdown — `secondsLeft`/`isHoldExpired` are computed each render from `hold.expires_at`
and a ticking `nowTick` state, not stored as their own state kept in sync via `setState`-in-effect,
per `eslint-plugin-react-hooks`'s newer `set-state-in-effect` rule, which caught this as a genuine
smell during implementation, not just a lint nag; inline 409 handling (`slot_unavailable` →
`error.details.alternatives` rendered as one-click retry buttons + an automatic availability
refetch). My Bookings: three tabs bucketed client-side from one unfiltered list fetch (the
`status` filter only accepts one value, and "Upcoming" needs `pending`+`confirmed` together), a
detail `Sheet` with the status-log timeline, a `Cancel` `AlertDialog` that shows the late-
cancellation warning from the new backend field, and an authenticated blob-download for
`calendar.ics` (the endpoint needs the JWT, so a plain `<a href>` can't be used). New shadcn
primitives: `badge`, `tabs`, `sheet`, `select`, `skeleton`, `alert-dialog` — hit the same Windows
path-alias bug as Section 8 (files landed in a literal `./@/` folder instead of `src/components/
ui/`), fixed the same way (moved by hand, no config change needed since it's a CLI-environment
quirk, not a project misconfiguration).

**What I changed / rejected:** No changes on review — the plan's decisions (deriving the provider
selector from availability instead of a nonexistent filter endpoint, the `would_be_late_cancellation`
addition, the morning/12/afternoon/18/evening boundary choice, per-click idempotency keys, client-
side tab bucketing) were accepted as-is. One real implementation fix made during typecheck/lint,
not a design change: the first draft tracked `selectedDate`/`secondsLeft`/`holdExpired` as separate
`useState` values kept in sync via `useEffect`, which `eslint-plugin-react-hooks`'s
`set-state-in-effect` rule flagged as an anti-pattern (React's own current guidance: prefer deriving
during render over syncing state via an effect) — refactored to compute `selectedDate` as `pickedDate
plus filteredDates` and `secondsLeft`/`isHoldExpired` as `hold plus nowTick`, both pure derivations,
with the interval effect only ticking a clock (a legitimate "subscribe to an external system" use of
an effect) rather than computing application state itself.

**Why:** The `POST /bookings/` schema bug mattered specifically because Section 9's whole hold→
countdown→confirm flow depends on the create response actually containing `id`/`status`/
`expires_at` — had it shipped undetected, `tsc` would have blocked every subsequent use of the hold
object, forcing a hand-written override type at exactly the point CLAUDE.md and this section's own
acceptance criterion ("no hand-written API response types") explicitly rule out; tracing *why*
`extend_schema` was ignored (rather than just special-casing the response type in the frontend)
kept the fix general enough that any future endpoint hitting the same generic-view-mixin pattern
won't need re-discovering it. The manual verification session surfaced two testing artifacts worth
recording so they're not mistaken for app bugs later: (1) a slow first `submit` response (several
minutes, not the usual sub-second) that looked like a frontend hang until a direct `curl` against
the backend proved the request had actually completed successfully — the UI was correct the whole
time, the dev environment's WSL/Windows Postgres round-trip was just unusually slow under repeated
concurrent test traffic; (2) the header's user-menu dropdown did not open under the browser tool's
*emulated* mobile viewport specifically, while the identical code opened correctly the instant the
same tab was switched back to desktop width — isolated to the test tool's touch-emulation layer,
not the app, since Radix's dropdown needs no code of ours to handle real mobile touch correctly.
Both are noted here rather than silently omitted, per the same "disclose testing limitations
honestly" standard applied to the token-refresh-retry path in Section 8. The required two-browser
race test (acceptance criterion's own wording) was run for real: two genuine browser tabs, two
different logged-in customers, racing an identical open slot with both clicks fired in the same
tool batch — one tab won the hold, the other got the exact "This time was just taken" + one-click
alternatives + auto-refreshed grid the spec calls for, which is the actual exclusion-constraint
guarantee from Section 5/6 surfacing correctly through the full stack, not just a unit-level claim.
