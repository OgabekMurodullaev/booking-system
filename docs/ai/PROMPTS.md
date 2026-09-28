# Section prompts — Booking System

How to use:
1. Put `CLAUDE.md` in the repo root before Section 1.
2. Paste one section at a time into Claude Code. Start in plan mode, approve the plan, let it build.
3. Review the diff yourself, run the app, then commit. After each section add 1–2 lines to `docs/AI_USAGE.md`
   (what AI generated, what you changed or rejected, and why).
4. Do not start the next section until the current one's acceptance criteria all pass.

---

## Section 1 — Monorepo, Docker (dev), settings

### Context
Section 1 / 12. Empty repo, only `CLAUDE.md` exists.

### Goal
A runnable dev environment: Django + Postgres + Redis + Celery in Docker, with clean split settings.

### Requirements
- Monorepo layout exactly as in CLAUDE.md §3 (create empty app packages for all apps listed).
- `backend/pyproject.toml` (or requirements files: `base.txt`, `dev.txt`, `prod.txt`) with pinned versions.
- Settings split: `base.py`, `dev.py`, `test.py`, `prod.py`; all config via `django-environ`; `.env.example`.
- Business-rule settings from CLAUDE.md §6 defined in `base.py`.
- `docker-compose.yml` (dev): `db` (postgres:16), `redis` (redis:7), `web` (runserver, bind-mounted code), `worker`, `beat`. Healthchecks on db and redis; web waits for healthy db.
- `backend/Dockerfile` (multi-stage, non-root user).
- `config/celery.py` wired up.
- DRF + drf-spectacular configured; `/api/schema/` and `/api/docs/` work.
- `GET /api/v1/health/` returns db + redis status (200 if both ok, 503 otherwise).
- `apps/common/exceptions.py` with base `DomainError(code, message, details, http_status)` and a DRF exception handler producing the error format from CLAUDE.md §7 (also for DRF's own ValidationError / auth errors).
- ruff config, pytest config (`DJANGO_SETTINGS_MODULE=config.settings.test`), `conftest.py`.
- `Makefile` with: `up`, `down`, `migrate`, `test`, `lint`, `fmt`, `shell`, `seed`.
- `.gitignore`, `.editorconfig`.

### Constraints
- Do NOT create any domain models yet (User comes in Section 2 — do not run `migrate` before it).
- No SQLite anywhere.

### Acceptance criteria
- [ ] `docker compose up -d` brings all services to healthy/running.
- [ ] `curl localhost:8000/api/v1/health/` → 200 with db and redis ok.
- [ ] `/api/docs/` renders.
- [ ] `make test` runs (a smoke test for health endpoint + error handler format passes).
- [ ] `make lint` passes.

### At the end
Run tests and lint. Summarize decisions. Propose commit message(s). Do not commit.

---

## Section 2 — Custom User, roles, JWT auth

### Context
Section 2 / 12. Dev stack runs. No migrations applied yet.

### Goal
Custom user model with roles and timezone, and a complete JWT auth flow.

### Requirements
- `accounts.User` (AbstractBaseUser + PermissionsMixin): email as username, full_name, role, timezone (validated IANA name via `zoneinfo.available_timezones()`), business FK — nullable, but the FK target (`catalog.Business`) comes in Section 3, so add the field in Section 3's migration, not now. Custom manager (`create_user`, `create_superuser`).
- `AUTH_USER_MODEL` set before the first migration.
- Endpoints under `/api/v1/auth/`:
  - `POST register/` — creates **customer only** (role cannot be chosen by the client).
  - `POST login/` — returns access + refresh (+ user payload).
  - `POST refresh/` — rotation + blacklist enabled.
  - `POST logout/` — blacklists the refresh token.
  - `GET/PATCH me/` — profile; user can change full_name and timezone, not role or email.
- Password validation via Django validators. Email normalized to lowercase; uniqueness case-insensitive.
- Permission classes in `apps/common/permissions.py`: `IsCustomer`, `IsProvider`, `IsBusinessAdmin`.
- Throttling on login and register (e.g. 10/min per IP).
- Django admin for User.

### Constraints
- No role escalation path through any public endpoint.

### Acceptance criteria
- [ ] Register → login → me → refresh → logout works; refresh token unusable after logout.
- [ ] Registering with `role=admin` in the body still creates a customer.
- [ ] Duplicate email with different case is rejected.
- [ ] Invalid timezone rejected with the standard error format.
- [ ] Tests for all of the above pass; lint passes.

### At the end
Run tests and lint. Summarize decisions. Propose commit message(s). Do not commit.

---

## Section 3 — Core models, DB constraints, admin

### Context
Section 3 / 12. Auth works.

### Goal
All domain models with database-level invariants, plus admin-facing CRUD APIs.

### Requirements
- Models exactly per CLAUDE.md §5: `Business`, `Service`, `Provider`, `WorkingHours`, `TimeOff`, `Booking`, `BookingStatusLog`. Add `User.business` FK now.
- Migration with `BtreeGistExtension()` before any exclusion constraint.
- All constraints from CLAUDE.md §5 (exclusion ×2, unique idempotency, check constraints for duration, buffer, time ordering, pending⇔expires_at). Also: no overlapping `WorkingHours` intervals per provider/weekday (exclusion constraint on an int4/time range or validated in service + tested — explain the choice).
- DB indexes for: bookings by (provider, status), (customer, created_at), GiST on `blocked_range`.
- Admin-only APIs (`IsBusinessAdmin`, scoped to `request.user.business`):
  - `/api/v1/services/` — CRUD; DELETE = soft delete. Public (anonymous) GET list/detail of active services is allowed.
  - `/api/v1/providers/` — admin creates a provider together with its user account (email, full_name, temporary password), assigns services. Public GET list of active providers with their services.
  - `/api/v1/providers/{id}/working-hours/` — replace-all PUT (admin or the provider themselves) + GET.
  - `/api/v1/providers/{id}/time-off/` — CRUD (admin or the provider themselves).
- Django admin registered for all models (Booking admin read-mostly, with status log inline).
- Validation in services: service belongs to provider's business, working-hours intervals sane, time off start < end.

### Constraints
- No booking creation logic yet (Section 5). No availability logic yet (Section 4).
- An admin of business A must never see or modify data of business B — test it.

### Acceptance criteria
- [ ] Raw ORM test: inserting two overlapping active bookings for the same provider raises `IntegrityError`; a cancelled one does not block; adjacent ranges `[10:00,11:00)` and `[11:00,12:00)` are allowed.
- [ ] Buffer test: with 15 min buffer, `[10:00,11:00)` blocks a booking starting 11:10 for the same provider.
- [ ] Customer overlap constraint test.
- [ ] Soft-deleted service disappears from public list but existing bookings still reference it.
- [ ] Cross-business isolation tests pass.
- [ ] All tests + lint pass.

### At the end
Run tests and lint. Summarize decisions (explain the WorkingHours overlap choice). Propose commit message(s). Do not commit.

---

## Section 4 — Availability engine

### Context
Section 4 / 12. Models and constraints exist.

### Goal
A pure, well-tested function that computes free slots, and an endpoint exposing it.

### Requirements
- `scheduling/services/availability.py`:
  - `get_available_slots(service, date_from, date_to, provider=None, now=None) -> list[Slot]`
  - `Slot` = dataclass(start: datetime UTC, end: datetime UTC, provider_ids: list[int]).
  - Algorithm per provider per day:
    1. Build working intervals from `WorkingHours` in the business timezone for that local date, convert to UTC (use `zoneinfo`; handle DST gaps/overlaps correctly).
    2. Subtract `TimeOff` intervals.
    3. Subtract `blocked_range` of active bookings (pending not yet expired + confirmed).
    4. Generate candidate starts on the 15-min grid (grid aligned to local time), keep those where `[start, start + duration + buffer)` fits entirely in a free interval.
    5. Drop slots earlier than `now + min lead` or later than `now + max advance`.
  - Merge across providers: same start → one slot with several `provider_ids`.
  - Keep it efficient: fixed number of queries regardless of number of days/providers (prefetch everything for the range up front). Interval math in pure Python helpers (`subtract_intervals`, `merge_intervals`) with their own unit tests.
- Endpoint: `GET /api/v1/availability/?service=<id>&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD[&provider=<id>]` (public).
  - Dates are interpreted in the business timezone. Max 14 days. `date_from` not in the past.
  - Response: slots grouped by local date, each slot with `start`, `end` (UTC) and `provider_ids`; plus `timezone` of the business.
- `find_alternatives(service, around: datetime, provider=None, limit=3)` helper (used in Section 5).

### Constraints
- The function must be deterministic given `now` — no hidden `timezone.now()` inside the core logic.

### Acceptance criteria (tests)
- [ ] Simple day: 09:00–18:00, 60-min service, no bookings → correct first/last slot.
- [ ] Lunch break (two intervals) — no slot spans the break.
- [ ] Service + buffer does not fit at the end of the day → last slot excluded.
- [ ] Existing booking and time off are excluded; expired pending does NOT block; cancelled does NOT block.
- [ ] Min lead time and max advance respected.
- [ ] DST transition day in a DST timezone (e.g. Europe/Berlin) produces correct UTC slots.
- [ ] Two providers → merged slots with both ids.
- [ ] Query count is constant for 1 day vs 14 days (`django_assert_max_num_queries`).
- [ ] Inactive service/provider yields no slots.
- [ ] All tests + lint pass.

### At the end
Run tests and lint. Explain the algorithm and its complexity in the summary. Propose commit message(s). Do not commit.

---

## Section 5 — Booking flow, state machine, idempotency

### Context
Section 5 / 12. Availability engine works.

### Goal
The full booking lifecycle from CLAUDE.md §6, safe under concurrency.

### Requirements
- `bookings/services/booking.py`:
  - `create_hold(customer, service, start, provider=None, idempotency_key=None) -> Booking`
    - Validate: service active; provider active and offers service; start on grid; within lead/advance window; slot lies inside the provider's working hours and not in time off (reuse availability helpers — do not trust the client).
    - Inside `transaction.atomic()`: lazily cancel expired overlapping pendings for that provider, then insert. Catch `IntegrityError` from the exclusion constraints → `SlotUnavailable` (409) with `alternatives` via `find_alternatives`. Distinguish provider conflict vs. customer's own overlap (`customer_overlap` code) by constraint name.
    - Auto-assign when provider is None (CLAUDE.md §6).
    - Idempotency: existing booking with same (customer, key) → return it (flag so the view returns 200).
    - Snapshot price and duration.
  - `submit_booking(booking, actor)`, `confirm_booking`, `cancel_booking(booking, actor, reason)`, `complete_booking` — all go through a single `transition_booking(booking, to_status, actor, reason)` that:
    - locks the row (`select_for_update`), re-checks the state machine table and actor permission,
    - sets `is_late_cancellation` when applicable,
    - writes `BookingStatusLog`,
    - enqueues notification tasks with `transaction.on_commit` (tasks can be stubs until Section 7).
  - `expire_stale_holds(now)` — bulk-expire, one log row per booking, returns count.
- Endpoints under `/api/v1/bookings/`:
  - `POST /` (customer) — create hold; supports `Idempotency-Key` header; 201 new / 200 replay.
  - `GET /` — role-aware list: customer → own; provider → own schedule; admin → whole business. Filters: status, date range, provider, service. Ordered by start.
  - `GET /{id}/` — includes status history (this is "booking history").
  - `POST /{id}/submit/`, `/confirm/`, `/cancel/` (body: reason), `/complete/`.
- Celery beat schedule for `expire_stale_holds` every minute.

### Constraints
- No business logic in views or serializers. No transition may bypass `transition_booking`.
- Never return another customer's booking (404, not 403, to avoid leaking existence).

### Acceptance criteria (tests)
- [ ] Happy path: hold → submit → (auto_confirm) confirmed; and hold → submit → provider confirm.
- [ ] Hold expiry (time-machine): expired hold cannot be submitted; slot becomes available again; lazy expiry lets a new customer book the slot even without beat.
- [ ] Every invalid transition in the state machine returns 409; every wrong actor returns 403.
- [ ] Late cancellation flagged; completing before end time rejected.
- [ ] 409 response contains up to 3 valid alternatives.
- [ ] Idempotent replay returns the same booking and creates no duplicate.
- [ ] Auto-assign picks the least-busy free provider.
- [ ] Booking outside working hours / in time off / not on grid / in the past → 400 with clear codes.
- [ ] Status log has a row for every transition, with actor.
- [ ] All tests + lint pass.

### At the end
Run tests and lint. Summarize decisions and list edge cases handled. Propose commit message(s). Do not commit.

---

## Section 6 — Concurrency & edge-case hardening

### Context
Section 6 / 12. Booking flow works functionally.

### Goal
Prove the system is race-safe and document the edge cases.

### Requirements
- Concurrency tests (`transaction=True`, real threads, `threading.Barrier` to release them simultaneously, each thread with its own DB connection closed at the end):
  - 10 customers book the same provider slot at once → exactly 1 success, 9 × 409.
  - Auto-assign with 3 providers and 5 concurrent requests → exactly 3 successes, each on a different provider.
  - Same customer, same Idempotency-Key, 5 concurrent requests → exactly 1 booking.
  - Concurrent confirm + cancel on the same pending booking → final state is consistent and the log has no impossible transition.
- Review the code for remaining races (e.g. check-then-act in services) and fix them.
- Create `docs/EDGE_CASES.md`: table of edge case → how it is handled → which test proves it. Include everything from Sections 3–5 plus: provider adds time off over an existing confirmed booking (allowed; booking stays; admin sees a warning flag in list via annotation — implement the flag), service price/duration changed after booking (snapshots), service deactivated with future bookings (existing bookings unaffected, no new ones), customer changes timezone (stored data unaffected — UTC).

### Acceptance criteria
- [ ] Concurrency tests pass 20 runs in a row (`pytest --count=20` via `pytest-repeat` for these tests only).
- [ ] `EDGE_CASES.md` complete, every row references a test.
- [ ] All tests + lint pass.

### At the end
Run tests and lint. Explain why the exclusion constraint (not `select_for_update` alone) is the core guarantee. Propose commit message(s). Do not commit.

---

## Section 7 — Notifications (Celery, email, .ics)

### Context
Section 7 / 12. Core backend complete.

### Goal
Reliable async notifications and a lightweight calendar integration.

### Requirements
- Celery tasks in `notifications/tasks.py`: `send_booking_confirmed`, `send_booking_cancelled`, `send_booking_pending_approval` (to provider), `send_booking_reminder` (24h before, scheduled by beat scan every 15 min with a `reminder_sent_at` field to avoid duplicates).
- Tasks are idempotent and use `autoretry_for`, exponential backoff, `max_retries=5`.
- Email via Django email backend (console in dev; SMTP settings from env in prod). Plain-text + HTML templates. Times rendered in the recipient's timezone.
- Confirmation email attaches an `.ics` (built with the `icalendar` library): UID stable per booking, so a cancellation sends a `METHOD:CANCEL` with the same UID.
- `GET /api/v1/bookings/{id}/calendar.ics` — download for the owner.

### Acceptance criteria
- [ ] Tests with `CELERY_TASK_ALWAYS_EAGER` / `mail.outbox`: correct recipients, timezone-correct times, attachment present and parseable.
- [ ] Notifications are only sent after commit (a rolled-back transition sends nothing — test it).
- [ ] Reminder not sent twice.
- [ ] All tests + lint pass.

### At the end
Run tests and lint. Summarize. Propose commit message(s). Do not commit.

---

## Section 8 — Frontend foundation: setup, auth, API client

### Context
Section 8 / 12. Backend API complete and documented at `/api/schema/`.

### Goal
A typed React app skeleton with working authentication and role-based routing.

### Requirements
- `frontend/`: Vite + React + TS (strict), Tailwind, shadcn/ui, TanStack Query, React Router, react-hook-form + zod, date-fns + date-fns-tz. ESLint + Prettier.
- `npm run gen:api` → `openapi-typescript` generates `src/api/schema.d.ts` from the backend schema; `src/api/client.ts` uses `openapi-fetch`.
- Auth: access token in memory, refresh token in localStorage; automatic refresh on 401 with a single in-flight refresh (no refresh storms); logout clears everything.
- Central error handling: parse the backend error format into a typed `ApiError`; toast for unexpected errors.
- Routes: `/login`, `/register`, customer area `/`, provider area `/provider`, admin area `/admin`; route guards by role; redirect after login by role.
- Login page has **demo buttons**: "Try as Customer / Provider / Admin" (credentials from `VITE_DEMO_*` env, shown only when set).
- Layout: header with user menu, business timezone indicator, responsive (mobile-first).
- Vite dev proxy `/api` → backend.
- `frontend/Dockerfile` (multi-stage: build with Node, output static files).

### Acceptance criteria
- [ ] `npm run typecheck`, `npm run lint`, `npm run build` pass.
- [ ] Register, login, logout, role redirect, token refresh work against the dev backend.
- [ ] No hand-written API response types.

### At the end
Summarize decisions. Propose commit message(s). Do not commit.

---

## Section 9 — Frontend: customer booking flow

### Context
Section 9 / 12. Frontend foundation and auth work.

### Goal
The core product experience: find a service, pick a slot, book it — delightful and clear.

### Requirements
- Services page: cards (name, duration, price formatted in UZS, description).
- Booking page for a service:
  - Provider selector with an **"Any available"** option (default).
  - Date strip / calendar for the next 14 days; days with no slots are disabled.
  - Slot grid grouped by morning / afternoon / evening, in the business timezone, with a visible "Tashkent time" label.
  - Selecting a slot creates a **hold** (send a generated `Idempotency-Key`), then shows a confirmation panel with a **10:00 countdown**; on expiry show "Hold expired" and refresh slots.
  - "Confirm booking" → submit. Show result state: confirmed, or "waiting for approval".
  - On 409: inline message "This time was just taken" + the returned alternatives as one-click buttons; refetch slots.
- My bookings page: tabs Upcoming / Past / Cancelled; each card shows status badge, time, provider, price; detail drawer with status history timeline; Cancel button with reason and a warning if inside the cancellation window (late cancellation); "Add to calendar" (.ics download).
- Loading skeletons, empty states, error states everywhere. Mutations invalidate the right queries.

### Acceptance criteria
- [ ] Full flow works end-to-end against the backend, including hold expiry and 409 alternatives (test by booking the same slot from two browsers).
- [ ] Works on a 375px wide screen.
- [ ] typecheck, lint, build pass.

### At the end
Summarize UX decisions. Propose commit message(s). Do not commit.

---

## Section 10 — Frontend: provider & admin panels

### Context
Section 10 / 12. Customer flow done.

### Goal
The business side: providers run their day, admins run the business.

### Requirements
- Provider:
  - Schedule view: day and week (simple custom grid is fine), bookings colored by status; the time-off warning flag visible.
  - Pending approvals list with Confirm / Reject (reject = cancel with reason).
  - Mark completed (enabled only after the booking ends).
  - Working hours editor (per weekday, multiple intervals, validation mirrors backend) and time-off manager.
- Admin:
  - Services CRUD (form with zod validation matching backend limits; soft delete).
  - Providers: create (with account), assign services, deactivate.
  - All bookings table: filters (status, provider, service, date range), pagination.
  - Dashboard: today's bookings, bookings per day (last 14 days, chart via recharts), cancellation rate, late cancellation count, provider utilization % (booked minutes / working minutes). Add one backend endpoint `GET /api/v1/stats/` (admin only) that computes these with aggregate queries — with tests.

### Acceptance criteria
- [ ] Provider and admin flows work end-to-end with demo data.
- [ ] Stats endpoint tested (numbers verified against fixture data, constant query count).
- [ ] typecheck, lint, build, backend tests pass.

### At the end
Summarize. Propose commit message(s). Do not commit.

---

## Section 11 — Production deploy (Hetzner VPS), CI/CD

### Context
Section 11 / 12. App complete locally. Target: Hetzner VPS, Ubuntu, Docker installed, domain `${DOMAIN}` (or `<ip>.sslip.io`).

### Goal
A secure, reproducible one-command deploy with CI.

### Requirements
- `deploy/docker-compose.prod.yml`: caddy, web (gunicorn, 3 workers, non-root), worker, beat, db (volume, not exposed), redis (not exposed). Restart policies, healthchecks, resource-sane defaults, log rotation.
- `deploy/Caddyfile`: `{$DOMAIN}`, `/api/*`, `/admin/*`, `/static/*` → web (Django static via whitenoise or Caddy file_server); everything else → React build with SPA fallback to `index.html`; gzip/zstd; security headers.
- Frontend build baked into the Caddy image (multi-stage) so the server needs no Node.
- `prod.py`: `DEBUG=False`, `SECURE_*`, HSTS, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS` from env, `SECURE_PROXY_SSL_HEADER`.
- `deploy/entrypoint.sh`: wait for db, `migrate`, `collectstatic`.
- `deploy/backup.sh`: daily `pg_dump` gzip with 7-day retention (document the cron line).
- GitHub Actions:
  - `ci.yml` on push/PR: backend (Postgres + Redis services, ruff, pytest), frontend (typecheck, lint, build).
  - `deploy.yml` on push to `main` after CI passes: SSH to VPS (secrets: host, user, key), `git pull`, `docker compose -f deploy/docker-compose.prod.yml up -d --build`, run migrations, smoke-check `/api/v1/health/`.
- `docs/DEPLOY.md`: server hardening checklist (non-root user, SSH keys only, ufw 22/80/443, fail2ban, unattended-upgrades, swap), first-time setup steps, env vars list.

### Acceptance criteria
- [ ] Locally: `docker compose -f deploy/docker-compose.prod.yml up --build` serves the app on http://localhost with DEBUG off.
- [ ] CI workflow is valid (`act` or a dry push) and green.
- [ ] Deployed URL serves HTTPS, health 200, SPA deep links work on refresh.

### At the end
Summarize. List manual steps I must do on the server. Propose commit message(s). Do not commit.

---

## Section 12 — Seed data & documentation

### Context
Section 12 / 12. App deployed.

### Goal
Make the project instantly understandable and demoable for reviewers.

### Requirements
- `python manage.py seed_demo` (idempotent, `--reset` flag): one business "Demo Salon" (Asia/Tashkent), 3 providers with realistic working hours (one with a lunch break, one with upcoming time off), 5 services (varied durations, prices, buffers), 15 customers, ~60 bookings across past and next 14 days in all statuses with status logs; 3 demo accounts (customer / provider / admin) matching `VITE_DEMO_*`.
- `README.md`: one-paragraph pitch, live demo URL + demo credentials, screenshots/GIF, feature list, tech stack, quick start (3 commands), running tests, project structure, links to docs, CI badge.
- `docs/ARCHITECTURE.md`: diagram (Mermaid) of containers and request flow; data model ER diagram (Mermaid); why exclusion constraints; availability algorithm; booking lifecycle state diagram (Mermaid); hold + lazy expiry design; idempotency; timezone strategy; trade-offs and what I'd do next with more time (e.g. recurring bookings, payments, multi-business tenancy, WebSocket live slot updates, rate-limit per user).
- `docs/API.md`: short guide with the main flow as curl examples; link to Swagger.
- `docs/AI_USAGE.md`: consolidate my per-section notes into: tools used, workflow (CLAUDE.md + sectioned prompts + plan mode + review), concrete examples where AI output was wrong or suboptimal and how it was caught/fixed, what I verified manually.
- Verify every link, command and credential in the docs actually works.

### Acceptance criteria
- [ ] Fresh clone → quick start commands → working app with demo data.
- [ ] All Mermaid diagrams render on GitHub.
- [ ] Full test suite, lint, typecheck, build pass.

### At the end
Summarize. Propose commit message(s). Do not commit.
