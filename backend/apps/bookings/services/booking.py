from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from psycopg.types.range import Range

from apps.accounts.models import User
from apps.catalog.models import Provider, Service
from apps.common.exceptions import DomainError
from apps.notifications.services import (
    notify_booking_cancelled,
    notify_booking_completed,
    notify_booking_confirmed,
    notify_hold_created,
    notify_pending_approval,
)
from apps.scheduling.services.availability import (
    Slot,
    _local_midnight_to_utc,
    find_alternatives,
    get_available_slots,
)

from ..models import Booking, BookingStatusLog
from .validation import (
    validate_grid_alignment,
    validate_lead_and_advance,
    validate_working_hours_and_time_off,
)


@dataclass
class HoldResult:
    booking: Booking
    created: bool


# --- state machine -----------------------------------------------------------------


def _is_customer_owner(actor: User | None, booking: Booking) -> bool:
    return actor is not None and actor.id == booking.customer_id


def _is_provider_owner(actor: User | None, booking: Booking) -> bool:
    provider = getattr(actor, "provider_profile", None)
    return actor is not None and provider is not None and provider.id == booking.provider_id


def _is_business_admin(actor: User | None, booking: Booking) -> bool:
    return (
        actor is not None
        and actor.role == User.Role.ADMIN
        and actor.business_id == booking.provider.business_id
    )


def _is_system(actor: User | None, booking: Booking) -> bool:
    return actor is None


def _any(*checks: Callable[[User | None, Booking], bool]):
    def combined(actor: User | None, booking: Booking) -> bool:
        return any(check(actor, booking) for check in checks)

    return combined


def _check_submitted_and_not_expired(booking: Booking, now: datetime) -> None:
    if booking.submitted_at is None:
        raise DomainError("Booking has not been submitted.", code="not_submitted", http_status=409)
    if booking.expires_at is not None and booking.expires_at <= now:
        raise DomainError("This hold has expired.", code="hold_expired", http_status=409)


def _check_ended(booking: Booking, now: datetime) -> None:
    if now < booking.time_range.upper:
        raise DomainError(
            "Booking cannot be completed before it ends.",
            code="booking_not_yet_ended",
            http_status=409,
        )


@dataclass
class TransitionRule:
    actor_check: Callable[[User | None, Booking], bool]
    extra_check: Callable[[Booking, datetime], None] | None = None


STATE_MACHINE: dict[tuple[str, str], TransitionRule] = {
    (Booking.Status.PENDING, Booking.Status.CONFIRMED): TransitionRule(
        actor_check=_any(_is_provider_owner, _is_business_admin, _is_system),
        extra_check=_check_submitted_and_not_expired,
    ),
    (Booking.Status.PENDING, Booking.Status.CANCELLED): TransitionRule(
        actor_check=_any(_is_customer_owner, _is_provider_owner, _is_business_admin, _is_system),
    ),
    (Booking.Status.CONFIRMED, Booking.Status.CANCELLED): TransitionRule(
        actor_check=_any(_is_customer_owner, _is_provider_owner, _is_business_admin),
    ),
    (Booking.Status.CONFIRMED, Booking.Status.COMPLETED): TransitionRule(
        actor_check=_any(_is_provider_owner, _is_business_admin),
        extra_check=_check_ended,
    ),
}


def _notify_transition(booking: Booking, to_status: str) -> None:
    if to_status == Booking.Status.CONFIRMED:
        notify_booking_confirmed(booking)
    elif to_status == Booking.Status.CANCELLED:
        notify_booking_cancelled(booking)
    elif to_status == Booking.Status.COMPLETED:
        notify_booking_completed(booking)


def transition_booking(
    booking: Booking,
    to_status: str,
    actor: User | None,
    reason: str = "",
    now: datetime | None = None,
) -> Booking:
    now = now or timezone.now()
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("provider__business", "customer")
            .get(pk=booking.pk)
        )
        rule = STATE_MACHINE.get((booking.status, to_status))
        if rule is None:
            raise DomainError(
                f"Cannot transition booking from {booking.status} to {to_status}.",
                code="invalid_transition",
                http_status=409,
            )
        if not rule.actor_check(actor, booking):
            raise DomainError(
                "You are not allowed to perform this transition.",
                code="permission_denied",
                http_status=403,
            )
        if rule.extra_check is not None:
            rule.extra_check(booking, now)

        from_status = booking.status
        booking.status = to_status

        if to_status == Booking.Status.CONFIRMED:
            booking.expires_at = None
        elif to_status == Booking.Status.CANCELLED:
            booking.cancellation_reason = reason
            booking.expires_at = None
            if (
                from_status == Booking.Status.CONFIRMED
                and actor is not None
                and actor.id == booking.customer_id
            ):
                window = timedelta(hours=booking.provider.business.cancellation_window_hours)
                if now >= booking.time_range.lower - window:
                    booking.is_late_cancellation = True

        booking.save()
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        transaction.on_commit(lambda: _notify_transition(booking, to_status))

    return booking


def confirm_booking(booking: Booking, actor: User | None, now: datetime | None = None) -> Booking:
    return transition_booking(booking, Booking.Status.CONFIRMED, actor, now=now)


def cancel_booking(
    booking: Booking, actor: User | None, reason: str = "", now: datetime | None = None
) -> Booking:
    return transition_booking(booking, Booking.Status.CANCELLED, actor, reason=reason, now=now)


def complete_booking(booking: Booking, actor: User | None, now: datetime | None = None) -> Booking:
    return transition_booking(booking, Booking.Status.COMPLETED, actor, now=now)


def submit_booking(booking: Booking, actor: User, now: datetime | None = None) -> Booking:
    now = now or timezone.now()
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("provider__business", "customer")
            .get(pk=booking.pk)
        )
        if booking.status != Booking.Status.PENDING:
            raise DomainError(
                f"Cannot submit a booking with status {booking.status}.",
                code="invalid_transition",
                http_status=409,
            )
        if actor.id != booking.customer_id:
            raise DomainError(
                "You are not allowed to submit this booking.",
                code="permission_denied",
                http_status=403,
            )
        if booking.submitted_at is not None:
            raise DomainError(
                "Booking has already been submitted.", code="invalid_transition", http_status=409
            )
        if booking.expires_at is not None and booking.expires_at <= now:
            raise DomainError("This hold has expired.", code="hold_expired", http_status=409)

        booking.submitted_at = now
        business = booking.provider.business

        if business.auto_confirm:
            booking.save(update_fields=["submitted_at"])
            return transition_booking(
                booking, Booking.Status.CONFIRMED, actor=None, reason="auto_confirm", now=now
            )

        booking.expires_at = min(
            booking.submitted_at + timedelta(hours=24),
            booking.time_range.lower - timedelta(hours=1),
        )
        booking.save(update_fields=["submitted_at", "expires_at"])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=booking.status,
            to_status=booking.status,
            actor=actor,
            reason="submitted",
        )
        transaction.on_commit(lambda: notify_pending_approval(booking))

    return booking


# --- hold creation -------------------------------------------------------------------


def _constraint_name(exc: IntegrityError) -> str | None:
    cause = exc.__cause__
    diag = getattr(cause, "diag", None)
    return getattr(diag, "constraint_name", None) if diag else None


def _is_deadlock(exc: OperationalError) -> bool:
    # Exclusion constraints under heavy concurrent contention on the same range can
    # occasionally deadlock (Postgres SQLSTATE 40P01) rather than raise a clean
    # IntegrityError. The deadlock victim's transaction is rolled back automatically;
    # treating it the same as a lost conflict (try the next candidate, or fail with
    # slot_unavailable) is correct and avoids leaking a raw 500 to the client.
    cause = exc.__cause__
    return getattr(cause, "sqlstate", None) == "40P01"


def _serialize_alternatives(slots: list[Slot]) -> list[dict]:
    return [
        {
            "start": slot.start.isoformat(),
            "end": slot.end.isoformat(),
            "provider_ids": slot.provider_ids,
        }
        for slot in slots
    ]


def _active_bookings_today_count(provider: Provider, local_date, zone: ZoneInfo) -> int:
    day_start = _local_midnight_to_utc(local_date, zone)
    day_end = _local_midnight_to_utc(local_date + timedelta(days=1), zone)
    return Booking.objects.filter(
        provider=provider,
        status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
        time_range__overlap=Range(day_start, day_end),
    ).count()


def _auto_assign_candidates(service: Service, start: datetime, now: datetime) -> list[Provider]:
    zone = ZoneInfo(service.business.timezone)
    local_date = start.astimezone(zone).date()
    slots = get_available_slots(
        service=service, date_from=local_date, date_to=local_date, provider=None, now=now
    )
    matching = next((slot for slot in slots if slot.start == start), None)
    if matching is None:
        return []
    providers = list(Provider.objects.filter(id__in=matching.provider_ids))
    providers.sort(key=lambda p: (_active_bookings_today_count(p, local_date, zone), p.id))
    return providers


def _expire_overlapping_stale_holds(
    provider: Provider, start: datetime, blocked_end: datetime, now: datetime
) -> None:
    stale = Booking.objects.filter(
        provider=provider,
        status=Booking.Status.PENDING,
        expires_at__lte=now,
        blocked_range__overlap=Range(start, blocked_end),
    )
    for booking in stale:
        transition_booking(booking, Booking.Status.CANCELLED, actor=None, reason="expired", now=now)


def create_hold(
    *,
    customer: User,
    service: Service,
    start: datetime,
    provider: Provider | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> HoldResult:
    now = now or timezone.now()

    if idempotency_key:
        existing = Booking.objects.filter(
            customer=customer, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return HoldResult(booking=existing, created=False)

    validate_grid_alignment(service.business, start)
    validate_lead_and_advance(start, now)

    end = start + timedelta(minutes=service.duration_minutes)
    blocked_end = end + timedelta(minutes=service.buffer_minutes)

    if provider is not None:
        validate_working_hours_and_time_off(provider, start, end)
        candidates = [provider]
    else:
        candidates = _auto_assign_candidates(service, start, now)
        if not candidates:
            alternatives = find_alternatives(service, around=start, provider=None, now=now)
            raise DomainError(
                "No provider is available for this slot.",
                code="slot_unavailable",
                details={"alternatives": _serialize_alternatives(alternatives)},
                http_status=409,
            )

    for candidate in candidates:
        try:
            with transaction.atomic():
                _expire_overlapping_stale_holds(candidate, start, blocked_end, now)
                booking = Booking.objects.create(
                    customer=customer,
                    provider=candidate,
                    service=service,
                    time_range=Range(start, end),
                    blocked_range=Range(start, blocked_end),
                    status=Booking.Status.PENDING,
                    price_snapshot=service.price,
                    duration_snapshot=service.duration_minutes,
                    expires_at=now + timedelta(minutes=settings.BOOKING_HOLD_TTL_MINUTES),
                    idempotency_key=idempotency_key,
                )
                BookingStatusLog.objects.create(
                    booking=booking,
                    from_status="",
                    to_status=Booking.Status.PENDING,
                    actor=customer,
                    reason="hold_created",
                )
                transaction.on_commit(lambda b=booking: notify_hold_created(b))
            return HoldResult(booking=booking, created=True)
        except (IntegrityError, OperationalError) as exc:
            if isinstance(exc, OperationalError) and not _is_deadlock(exc):
                raise

            constraint = _constraint_name(exc) if isinstance(exc, IntegrityError) else None

            # A concurrent request may have violated *both* the idempotency-key
            # uniqueness and a provider/customer exclusion constraint at once (e.g.
            # two truly identical concurrent replays of the same hold), or lost a
            # deadlock against the winning insert; Postgres/our own retry loop only
            # ever sees one outcome. Whenever a key was given, check for a winning
            # replay first, regardless of what this specific attempt failed with.
            if idempotency_key:
                existing = Booking.objects.filter(
                    customer=customer, idempotency_key=idempotency_key
                ).first()
                if existing is not None:
                    return HoldResult(booking=existing, created=False)

            if constraint == "booking_no_customer_overlap":
                raise DomainError(
                    "You already have a booking that overlaps this time.",
                    code="customer_overlap",
                    http_status=409,
                ) from exc
            continue

    alternatives = find_alternatives(service, around=start, provider=provider, now=now)
    raise DomainError(
        "This time is no longer available.",
        code="slot_unavailable",
        details={"alternatives": _serialize_alternatives(alternatives)},
        http_status=409,
    )


def expire_stale_holds(now: datetime) -> int:
    count = 0
    stale_ids = list(
        Booking.objects.filter(status=Booking.Status.PENDING, expires_at__lte=now).values_list(
            "id", flat=True
        )
    )
    for booking_id in stale_ids:
        booking = Booking.objects.filter(pk=booking_id).first()
        if booking is None:
            continue
        try:
            transition_booking(
                booking, Booking.Status.CANCELLED, actor=None, reason="expired", now=now
            )
            count += 1
        except DomainError:
            continue
    return count
