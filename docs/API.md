# API Guide

Full interactive reference (every endpoint, every field): **`/api/docs/`** (Swagger UI), schema
at **`/api/schema/`**. This page is just the core flow as real `curl` examples — every response
below was actually captured from a running dev server against seeded demo data, not written
from memory of the schema.

All requests are JSON. Errors always come back as `{"error": {"code", "message", "details"}}`.
Datetimes are ISO 8601 UTC (`Z` suffix) in every response; convert to a local timezone on
display, never on the wire.

## 1. Log in

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"demo.customer@bookingsystem.test","password":"DemoPass123!"}'
```

```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {"id": 123, "email": "demo.customer@bookingsystem.test", "full_name": "Demo Customer", "role": "customer", "timezone": "Asia/Tashkent", "provider_id": null}
}
```

`access` is good for 15 minutes; send it as `Authorization: Bearer <access>` on every
subsequent request. Refresh with `POST /api/v1/auth/refresh/` (`{"refresh": "..."}`) before it
expires — refresh tokens rotate and the old one is blacklisted on use.

## 2. Check availability

```bash
curl "http://localhost:8000/api/v1/availability/?service=59&date_from=2026-09-29&date_to=2026-10-02" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "timezone": "Asia/Tashkent",
  "dates": [
    {"date": "2026-09-29", "slots": []},
    {"date": "2026-09-30", "slots": [
      {"start": "2026-09-30T04:00:00Z", "end": "2026-09-30T04:30:00Z", "provider_ids": [20, 22]},
      {"start": "2026-09-30T04:15:00Z", "end": "2026-09-30T04:45:00Z", "provider_ids": [20, 22]}
    ]}
  ]
}
```

Omit `provider` to see slots across every provider who offers the service (as above); pass
`provider=<id>` to check one specific provider. The date range is capped at 14 days per request.

## 3. Hold a slot

```bash
curl -X POST http://localhost:8000/api/v1/bookings/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: some-client-generated-uuid" \
  -d '{"service":59,"provider":20,"start":"2026-09-30T04:00:00Z"}'
```

If someone beat you to that exact slot in the meantime (this is a real captured response, not a
hypothetical — that slot really was taken between the availability check above and this call):

```json
{
  "error": {
    "code": "slot_unavailable",
    "message": "This time is no longer available.",
    "details": {
      "alternatives": [
        {"start": "2026-09-30T04:45:00+00:00", "end": "2026-09-30T05:15:00+00:00", "provider_ids": [20]}
      ]
    }
  }
}
```

Otherwise, `201` with the new booking (`status: "pending"`, `expires_at` ~10 minutes out):

```json
{
  "id": 245, "status": "pending", "start": "2026-09-30T04:45:00Z", "end": "2026-09-30T05:15:00Z",
  "price_snapshot": "80000.00", "expires_at": "2026-09-29T14:08:04.785073Z", "submitted_at": null,
  "status_logs": [{"from_status": "", "to_status": "pending", "reason": "hold_created"}]
}
```

Send the same `Idempotency-Key` again with the same customer and you'll get this same booking
back with `200` instead of a duplicate `201` — safe to retry a timed-out request.

Omit `provider` entirely to auto-assign among whoever's free for that slot. On a real conflict
(not just this specific candidate, but every candidate), the same `slot_unavailable` shape comes
back with alternatives across *any* provider.

## 4. Submit it (starts the approval clock, or auto-confirms)

```bash
curl -X POST http://localhost:8000/api/v1/bookings/245/submit/ -H "Authorization: Bearer $TOKEN"
```

If the business has `auto_confirm=True`, this returns `status: "confirmed"` immediately. Demo
Salon doesn't, so it stays `"pending"` with `submitted_at` now set and `expires_at` pushed out to
the approval window — a provider or admin now needs to confirm it:

```bash
curl -X POST http://localhost:8000/api/v1/bookings/245/confirm/ \
  -H "Authorization: Bearer $PROVIDER_TOKEN"
```

## 5. Cancel

```bash
curl -X POST http://localhost:8000/api/v1/bookings/245/cancel/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Change of plans"}'
```

Cancelling a `confirmed` booking inside the business's `cancellation_window_hours` sets
`is_late_cancellation: true` on the response but still succeeds — the flag is informational,
not a block.

## Everything else

Providers/services CRUD, working hours, time off, the admin stats dashboard, and the full
request/response shape for every field above — see `/api/docs/`.
