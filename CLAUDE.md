# CLAUDE.md — Booking System (Mohirlar test task)

This file is the persistent context for every Claude Code session in this repo.
Read it fully before doing anything. If a request conflicts with this file, stop and ask.

## 1. Product in one paragraph

An appointment booking system for a small service business (e.g. a salon).
Customers pick a service, see real free time slots, and book one. The business
(admin + providers) manages services, providers, working hours, time off and bookings.
The core promise: **a slot can never be double-booked, even under concurrent requests.**

## 2. Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.x, Django REST Framework |
| DB | PostgreSQL 16 (required: range types, `btree_gist`, exclusion constraints) |
| Auth | `djangorestframework-simplejwt` (access 15 min, refresh 7 days, rotation + blacklist) |
| Async | Celery 5 + Redis 7 (worker + beat) |
| API docs | `drf-spectacular` (Swagger at `/api/docs/`, schema at `/api/schema/`) |
| Filtering | `django-filter` |
| Tests | `pytest`, `pytest-django`, `factory_boy`, `time-machine` |
| Lint | `ruff` (lint + format) |
| Frontend | Vite + React 18 + TypeScript, Tailwind, shadcn/ui, TanStack Query, React Router, react-hook-form + zod, date-fns + date-fns-tz |
| API client | `openapi-typescript` + `openapi-fetch` (types generated from backend schema — never hand-write API types) |
| Infra | Docker Compose, Caddy (reverse proxy + auto HTTPS), Hetzner VPS (Ubuntu), GitHub Actions |

## 3. Repository layout

```
backend/
  config/settings/{base,dev,test,prod}.py
  config/{urls,celery,wsgi}.py
  apps/
    common/        # base models, error handler, permissions, utils
    accounts/      # custom User (role, timezone), auth endpoints
    catalog/       # Business, Service, Provider
    scheduling/    # WorkingHours, TimeOff, services/availability.py
    bookings/      # Booking, BookingStatusLog, services/booking.py, state machine
    notifications/ # Celery tasks, email templates, .ics generation
  conftest.py
frontend/
  src/{api,features/{auth,booking,provider,admin},components/ui,lib,routes}
docs/              # ARCHITECTURE.md, EDGE_CASES.md, AI_USAGE.md, API.md
deploy/            # Caddyfile, prod compose, backup script
```

## 4. Architecture rules (non-negotiable)

1. **Thin views, fat services.** Views: auth, permissions, serializer validation, call a service, return a response.
   All business logic lives in `apps/<app>/services/*.py` as plain functions with type hints.
2. **Serializers validate input shape; services validate business rules.** Services raise
   domain exceptions from `apps/common/exceptions.py`; a single DRF exception handler maps them to HTTP.
3. **The database is the last line of defence.** Invariants that must never break are enforced by
   DB constraints (exclusion, unique, check), not only in Python.
4. **All datetimes are timezone-aware and stored in UTC.** Working hours are stored as local
   `time` values interpreted in the business timezone (`zoneinfo`). Convert at the edges only.
5. **Every booking status change goes through one function** (`transition_booking(...)`) that checks
   the state machine, checks the actor's permission, writes `BookingStatusLog`, and enqueues notifications
   via `transaction.on_commit`.
6. **No N+1 queries.** Use `select_related` / `prefetch_related`; add a query-count test for list endpoints.
7. **Soft delete** for `Service` and `Provider` (`is_active=False`). Never hard-delete anything that bookings reference.

## 5. Domain model

- `User`: email (login), full_name, role ∈ {customer, provider, admin}, timezone (IANA string), business FK (nullable; required for provider/admin).
- `Business`: name, timezone, auto_confirm (bool), cancellation_window_hours (default 24).
- `Service`: business, name, description, duration_minutes (5..480, multiple of 5), price (Decimal 12,2), buffer_minutes (0..120), is_active.
- `Provider`: user (1:1), business, services (M2M), is_active.
- `WorkingHours`: provider, weekday (0–6), start_time, end_time. Check: start < end. Multiple intervals per day allowed (lunch break = two intervals); intervals of the same provider/weekday must not overlap.
- `TimeOff`: provider, start (tz-aware), end, reason. Check: start < end.
- `Booking`:
  - customer, provider, service
  - `time_range` — `DateTimeTZRange` `[start, end)` of the appointment
  - `blocked_range` — `[start, end + buffer)`; this is what blocks the provider
  - status ∈ {pending, confirmed, cancelled, completed}
  - price_snapshot, duration_snapshot (copied from service at creation)
  - expires_at (nullable; only for pending), submitted_at (nullable)
  - is_late_cancellation (bool), cancellation_reason (text)
  - idempotency_key (nullable), created_at, updated_at
- `BookingStatusLog`: booking, from_status, to_status, actor (nullable = system), reason, created_at.

### DB constraints on Booking

- `ExclusionConstraint(provider =, blocked_range &&)` WHERE status IN (pending, confirmed) — **no provider double booking**.
- `ExclusionConstraint(customer =, time_range &&)` WHERE status IN (pending, confirmed) — a customer cannot be in two places at once.
- `UniqueConstraint(customer, idempotency_key)` WHERE idempotency_key IS NOT NULL.
- Check: `status = 'pending'` ⇔ `expires_at IS NOT NULL`.
- Requires migration `BtreeGistExtension()` before the constraints.

## 6. Business rules

| Rule | Value (setting in `base.py`) |
|---|---|
| Slot granularity | 15 min (`BOOKING_SLOT_STEP_MINUTES`) |
| Min lead time | 60 min before start (`BOOKING_MIN_LEAD_MINUTES`) |
| Max advance | 30 days (`BOOKING_MAX_ADVANCE_DAYS`) |
| Hold TTL (checkout) | 10 min (`BOOKING_HOLD_TTL_MINUTES`) |
| Approval TTL | pending after submit expires at `min(submitted_at + 24h, start - 1h)` |
| Availability query range | max 14 days per request |

### Booking lifecycle

1. **Hold** — `POST /api/v1/bookings/` creates `pending` with `expires_at = now + 10 min`. The slot is reserved.
2. **Submit** — `POST /api/v1/bookings/{id}/submit/` (customer, before hold expires):
   - `business.auto_confirm = True` → `confirmed`, `expires_at = NULL`.
   - else → stays `pending`, `submitted_at = now`, `expires_at` = approval TTL; provider/admin must confirm.
3. **Expiry** — pending bookings past `expires_at` become `cancelled` (reason `expired`, actor = system).
   Done two ways: Celery beat every minute (`expire_stale_holds`) **and** lazily inside the booking
   transaction (cancel expired pendings that overlap the requested range before inserting), so a stale
   hold never blocks a real customer even if beat is down.

### State machine

| From → To | Allowed actors | Extra rule |
|---|---|---|
| pending → confirmed | provider (own), admin (same business), system (auto_confirm on submit) | must be submitted and not expired |
| pending → cancelled | customer (own), provider (own), admin, system (expiry) | |
| confirmed → cancelled | customer (own), provider (own), admin | customer inside cancellation window → `is_late_cancellation = True` (allowed, flagged) |
| confirmed → completed | provider (own), admin | only after `time_range.upper` has passed |
| cancelled / completed → * | nobody | terminal states |

Invalid transition → 409 `invalid_transition`. Wrong actor → 403.

### Conflict handling

On a double-booking attempt, catch `IntegrityError` from the exclusion constraint, map it to
409 `slot_unavailable`, and include `alternatives`: the next 3 free slots for the same service
(same provider if one was requested, otherwise any provider), starting from the requested time.

### Auto-assign

If `provider` is omitted, pick among providers offering the service who are free for that slot,
ordered by fewest active bookings that day, then by id. Try to insert for each candidate in order;
on constraint conflict move to the next one. If all fail → 409 with alternatives.

## 7. API conventions

- Prefix: `/api/v1/`. JSON only. Plural resource names.
- Errors always: `{"error": {"code": "snake_case_code", "message": "Human readable", "details": {...}}}`.
- Pagination: page-number, `page_size` default 20, max 100.
- Datetimes in responses: ISO 8601 UTC (`Z`). Frontend converts to business timezone for display.
- `Idempotency-Key` header supported on `POST /bookings/`: same key + same customer → return the existing booking with 200 instead of 201.
- Every endpoint has `@extend_schema` with request/response serializers so the generated TS types are correct.

## 8. Testing rules

- Every service function has unit tests. Every endpoint has at least: happy path, validation error, permission error.
- Concurrency tests use `pytest.mark.django_db(transaction=True)` and real threads against real Postgres.
- Use `time-machine` to freeze time — never depend on the real clock in tests.
- Test DB is Postgres (never SQLite — constraints would silently not exist).

## 9. Commands

```bash
docker compose up -d                                  # dev stack: db, redis, web, worker, beat
docker compose exec web python manage.py migrate
docker compose exec web pytest -q
docker compose exec web ruff check . && docker compose exec web ruff format --check .
docker compose exec web python manage.py seed_demo    # demo data + demo accounts
cd frontend && npm run dev | npm run build | npm run typecheck | npm run gen:api
```

## 10. Working agreement for Claude

- Start every section in **plan mode**: show the plan (files to create/change, key decisions) and wait for approval.
- Work only on the current section's scope. Do not refactor unrelated code.
- Run tests + lint before declaring a section done. Never mark done with failing tests.
- **Never commit.** At the end, output: summary, decisions + trade-offs, anything uncertain, and a proposed
  Conventional Commit message (or several, if the section should be split into multiple commits).
- Never commit secrets. Config comes from environment variables (`django-environ`); keep `.env.example` updated.
- If you are unsure about a business rule, ask instead of guessing.
- Code, comments, docs and commit messages in English.
