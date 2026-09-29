# Booking System

![CI](https://github.com/OgabekMurodullaev/booking-system/actions/workflows/ci.yml/badge.svg)

An appointment booking system for a small service business (think a salon or a barbershop).
Customers pick a service, see real free time slots, and book one; the business (admin +
providers) manages services, providers, working hours, time off, and bookings. The core
promise: **a slot can never be double-booked, even under concurrent requests** — enforced at
the database level with Postgres exclusion constraints, not just checked in application code.

## Live demo

Not deployed yet — see [docs/DEPLOY.md](docs/DEPLOY.md) for the (unexercised-against-a-real-server)
production deploy path. Run it locally with the quick start below instead.

**Demo accounts** (created by `python manage.py seed_demo`, password `DemoPass123!` for all
three):

| Role | Email |
|---|---|
| Customer | `demo.customer@bookingsystem.test` |
| Provider | `demo.provider@bookingsystem.test` |
| Admin | `demo.admin@bookingsystem.test` |

The login page also has one-click "Try as Customer / Provider / Admin" buttons once
`frontend/.env` is set up (see quick start).

## Features

- **Customer**: browse services, see real availability (grouped by day, filtered by provider),
  hold a slot, submit for approval or auto-confirm, view/cancel own bookings, download a
  `.ics` calendar invite.
- **Provider**: day/week schedule view, approve/reject pending bookings, edit working hours
  (multiple intervals per day, e.g. a lunch break), manage time off.
- **Admin**: dashboard (bookings/day chart, cancellation rate, provider utilization), manage
  services and providers (soft delete), browse and filter every booking in the business.
- **Under the hood**: JWT auth with refresh rotation, idempotent booking creation
  (`Idempotency-Key` header), a hold → submit → confirm lifecycle with lazy + scheduled expiry,
  email notifications (Celery), and an availability engine that answers a 14-day, multi-provider
  query in a fixed, small number of database queries.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.x, Django REST Framework |
| DB | PostgreSQL 16 (exclusion constraints, `btree_gist`) |
| Auth | `djangorestframework-simplejwt` (access 15 min, refresh 7 days, rotation + blacklist) |
| API docs | `drf-spectacular` (Swagger at `/api/docs/`) |
| Async | Celery 5 + Redis 7 (worker + beat) |
| Tests | `pytest`, `pytest-django`, `factory_boy`, `time-machine` — 200 tests, real Postgres |
| Frontend | Vite + React 18 + TypeScript, Tailwind, shadcn/ui, TanStack Query, React Router |
| API client | `openapi-typescript` + `openapi-fetch` — types generated from the live backend schema |
| Infra | Docker Compose, Caddy (reverse proxy + auto HTTPS), GitHub Actions |

## Quick start

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
```

> These 3 commands themselves weren't run against a live Docker daemon in the environment
> this project was built in (Docker Desktop wasn't kept running there). Everything they call —
> `migrate` and `seed_demo` — was run and verified for real against the same Postgres/Redis the
> `docker-compose.yml` services provide, just via a native local setup instead of through
> Compose; the compose file's service definitions themselves are unchanged since Section 1.

Then open the frontend:

```bash
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

Backend: http://localhost:8000 (Swagger at `/api/docs/`). Frontend: http://localhost:5173.

## Running tests

```bash
docker compose exec web pytest -q                                 # backend (200 tests)
docker compose exec web ruff check . && ruff format --check .     # backend lint
cd frontend && npm run typecheck && npm run lint && npm run build # frontend
```

## Project structure

```
backend/
  config/settings/{base,dev,test,prod}.py
  apps/
    common/        # base models, error handler, permissions, seed_demo command
    accounts/      # custom User (role, timezone), auth endpoints
    catalog/       # Business, Service, Provider
    scheduling/    # WorkingHours, TimeOff, services/availability.py
    bookings/      # Booking, BookingStatusLog, services/booking.py, state machine
    notifications/ # Celery tasks, email templates, .ics generation
frontend/
  src/{api,auth,components,hooks,routes/{admin,provider}}
docs/              # architecture, API guide, deploy guide, edge cases, AI usage log
deploy/            # Caddyfile, prod compose, backup script
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, data model, the double-booking
  guarantee, availability algorithm, booking lifecycle, timezone strategy, trade-offs.
- [docs/API.md](docs/API.md) — the core flow as `curl` examples; full reference at `/api/docs/`.
- [docs/DEPLOY.md](docs/DEPLOY.md) — production deploy checklist for a Hetzner VPS.
- [docs/EDGE_CASES.md](docs/EDGE_CASES.md) — every handled edge case, each backed by a real test.
- [docs/AI_USAGE.md](docs/AI_USAGE.md) — how this project was built with AI assistance, what
  went wrong along the way and how it was caught.

## Screenshots

Not included yet — the project was built and tested through a running dev server rather than
a workflow that produces committable image assets. `seed_demo` gives you realistic data to
click through yourself in under five minutes via the quick start above.
