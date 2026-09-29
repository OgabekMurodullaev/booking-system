# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three roles, one shared system:

- **Customer** — self-serve: browse a business's services, see real-time free slots, hold and
  submit a booking, track/cancel it. No account needed to browse; account needed to book.
- **Provider** — staff member who fulfills appointments. Manages their own working hours and time
  off, confirms/cancels/completes bookings assigned to them.
- **Admin** — manages one business: its services, its providers, and oversight of all of that
  business's bookings.

Generic across any appointment-based small service business (salon, clinic, tutoring, fitness,
repair shop, etc.) — not modeled on one specific vertical. The domain model (`Business` → `Service`
+ `Provider`, `Booking`) makes no assumptions specific to any one business type.

## Product Purpose

Let a small service business take bookings online without ever double-booking a provider or a
customer, even under concurrent requests — and let customers self-serve the entire booking
lifecycle (find a slot, hold it, get confirmed, get reminded, cancel if needed) without staff
manually managing a calendar by hand.

## Operating Context

- Each `Business` is an independent tenant: its own timezone, services, providers, working hours,
  time off, and `auto_confirm` policy (bookings either need explicit provider/admin approval, or
  confirm automatically on submit).
- Customer flow: browse services → see availability (computed live from working hours, time off,
  and existing bookings) → hold a slot (10 min TTL) → submit → wait for confirmation (or
  auto-confirm) → attend, or cancel (a cancellation inside the business's cancellation window is
  flagged late, but still allowed).
- Provider flow: set working hours (multiple intervals/day allowed, e.g. a lunch-break gap),
  record time off, confirm/cancel/complete their own bookings.
- Admin flow: manage the business's services and providers (soft-delete only — deactivated
  services/providers are hidden from new bookings but never break bookings that already reference
  them), oversee every booking in the business.
- Background jobs (Celery beat): expire stale unconfirmed holds every minute so an abandoned hold
  never blocks a real customer; scan for bookings starting in ~24h every 15 min and send a
  reminder email exactly once.
- Notifications: email (console backend in dev, SMTP in prod) for pending-approval (to provider),
  confirmed, cancelled, and the 24h reminder; confirmed/cancelled emails carry a `.ics` calendar
  attachment with a stable UID so a cancellation correctly updates/removes the same calendar entry.

## Capabilities and Constraints

**Built (backend, Sections 1-7 of 12):** JWT auth with three roles; full catalog + scheduling +
booking CRUD; a DST-safe availability engine (`zoneinfo`-based UTC↔local conversion); the full
booking state machine (pending → confirmed/cancelled → completed) with idempotency-key support;
hard double-booking prevention enforced at the Postgres level via `ExclusionConstraint`s (not just
application checks) — proven stable under real concurrent-thread stress tests, not just
sequential ones; email notifications with `.ics` attachments and deduplicated reminders.

**Not yet built:** the frontend (Sections 8-10 — this section is the first of those), production
deployment (Section 11), and seed data/final docs (Section 12).

**Constraints:**
- All datetimes stored and reasoned about internally in UTC; converted to a local timezone only at
  the edges (working hours are stored as local `time` values interpreted via the business's IANA
  timezone; a user's own `timezone` field controls how times are *displayed* to them, and never
  changes what's stored).
- Multi-tenant: a provider/admin belongs to exactly one business; a customer can book across
  different businesses freely.
- API error responses follow one fixed envelope shape (`{"error": {"code","message","details"}}`)
  — the frontend's error handling should be built to parse this shape generically, not per-endpoint.
- Frontend must be mobile-first responsive (explicit requirement, not just a nice-to-have) since
  customers are expected to book from a phone as often as a desktop.
- No hand-written API response types on the frontend — types are generated from the backend's
  OpenAPI schema.

## Brand Commitments

None. No real business name, logo, or brand identity exists — "Booking System" is a working title
only. Do not invent a brand name, logo, or visual identity beyond what's needed for a generic,
white-label-feeling admin/booking tool.

## Evidence on Hand

None. This is a technical assessment project (not a product being sold to real customers) with no
real business, customer, testimonial, or asset data. Section 12's seed data will create clearly
fictional demo entities for demonstration only — future work must not present any of it as real.

## Product Principles

1. **Never double-book, provably.** The database is the last line of defence — every invariant
   that must never break is enforced by a DB constraint, not only application logic, and is proven
   under real concurrent load, not just a single-threaded happy path.
2. **UTC internally, local at the edges.** No screen or component should reason about time in
   anything but the viewer's own local time for display, or UTC for storage/transport — never mix
   the two.
3. **Role-appropriate surfaces, not one generic CRUD UI.** Customer self-service (lightweight,
   booking-funnel-like) and provider/admin tooling (dense, operational, schedule-oriented) are
   different jobs for different people and should feel different, even sharing one design system.
4. **Multi-tenant by business, always.** Every screen and query is implicitly scoped to "this
   business" (or "this provider") except the few genuinely public, cross-business views
   (e.g. browsing active services).
5. **Trust the backend's typed errors.** The API's `{"error": {code, message, details}}` envelope
   is the single source of truth for what went wrong; the frontend maps it generically rather than
   re-deriving validation logic client-side.

## Accessibility & Inclusion

Required standard: WCAG AA color contrast throughout; full keyboard navigation for every
interactive flow (no mouse-only interactions); visible focus states on all focusable elements;
every form input has an associated label (no placeholder-only labeling).
