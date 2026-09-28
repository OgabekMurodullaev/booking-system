from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from psycopg.types.range import Range

from apps.bookings.models import Booking


@pytest.fixture
def base_time():
    return timezone.now().replace(microsecond=0, minute=0, second=0) + timedelta(days=1)


def _range(base, start_offset_minutes, end_offset_minutes):
    return Range(
        base + timedelta(minutes=start_offset_minutes),
        base + timedelta(minutes=end_offset_minutes),
    )


def _create_booking(
    *, customer, provider, service, base_time, start, end, status="confirmed", **kwargs
):
    kwargs.setdefault("price_snapshot", "20.00")
    kwargs.setdefault("duration_snapshot", 30)
    return Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=_range(base_time, start, end),
        blocked_range=_range(base_time, start, end),
        status=status,
        **kwargs,
    )


@pytest.mark.django_db
def test_overlapping_active_bookings_same_provider_raise_integrity_error(
    customer, other_customer, provider, service, base_time
):
    _create_booking(
        customer=customer, provider=provider, service=service, base_time=base_time, start=0, end=60
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        _create_booking(
            customer=other_customer,
            provider=provider,
            service=service,
            base_time=base_time,
            start=30,
            end=90,
        )


@pytest.mark.django_db
def test_cancelled_booking_does_not_block(customer, other_customer, provider, service, base_time):
    _create_booking(
        customer=customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
        status="cancelled",
    )

    # Should succeed: the cancelled booking above does not participate in the exclusion.
    _create_booking(
        customer=other_customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
    )


@pytest.mark.django_db
def test_adjacent_bookings_same_provider_allowed(
    customer, other_customer, provider, service, base_time
):
    _create_booking(
        customer=customer, provider=provider, service=service, base_time=base_time, start=0, end=60
    )
    _create_booking(
        customer=other_customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=60,
        end=120,
    )


@pytest.mark.django_db
def test_buffer_blocks_booking_starting_within_buffer_window(
    customer, other_customer, provider, service, base_time
):
    # [10:00, 11:00) appointment with a 15-min buffer -> blocked_range [10:00, 11:15).
    Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=_range(base_time, 0, 60),
        blocked_range=_range(base_time, 0, 75),
        status="confirmed",
        price_snapshot="20.00",
        duration_snapshot=60,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(
            customer=other_customer,
            provider=provider,
            service=service,
            time_range=_range(base_time, 70, 100),
            blocked_range=_range(base_time, 70, 100),
            status="confirmed",
            price_snapshot="20.00",
            duration_snapshot=30,
        )


@pytest.mark.django_db
def test_customer_overlap_constraint(customer, provider, other_provider, service, base_time):
    _create_booking(
        customer=customer, provider=provider, service=service, base_time=base_time, start=0, end=60
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        _create_booking(
            customer=customer,
            provider=other_provider,
            service=service,
            base_time=base_time,
            start=30,
            end=90,
        )


@pytest.mark.django_db
def test_pending_requires_expires_at(customer, provider, service, base_time):
    with pytest.raises(IntegrityError), transaction.atomic():
        _create_booking(
            customer=customer,
            provider=provider,
            service=service,
            base_time=base_time,
            start=0,
            end=60,
            status="pending",
        )


@pytest.mark.django_db
def test_confirmed_must_not_have_expires_at(customer, provider, service, base_time):
    with pytest.raises(IntegrityError), transaction.atomic():
        _create_booking(
            customer=customer,
            provider=provider,
            service=service,
            base_time=base_time,
            start=0,
            end=60,
            status="confirmed",
            expires_at=timezone.now() + timedelta(minutes=10),
        )


@pytest.mark.django_db
def test_pending_with_expires_at_succeeds(customer, provider, service, base_time):
    _create_booking(
        customer=customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
        status="pending",
        expires_at=timezone.now() + timedelta(minutes=10),
    )


@pytest.mark.django_db
def test_idempotency_key_unique_per_customer(
    customer, provider, other_provider, service, base_time
):
    _create_booking(
        customer=customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
        idempotency_key="key-1",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        _create_booking(
            customer=customer,
            provider=other_provider,
            service=service,
            base_time=base_time,
            start=120,
            end=180,
            idempotency_key="key-1",
        )


@pytest.mark.django_db
def test_idempotency_key_can_repeat_across_customers(
    customer, other_customer, provider, other_provider, service, base_time
):
    _create_booking(
        customer=customer,
        provider=provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
        idempotency_key="shared-key",
    )
    _create_booking(
        customer=other_customer,
        provider=other_provider,
        service=service,
        base_time=base_time,
        start=0,
        end=60,
        idempotency_key="shared-key",
    )


@pytest.mark.django_db
def test_deactivated_service_still_referenced_by_existing_booking(
    customer, provider, service, base_time
):
    booking = _create_booking(
        customer=customer, provider=provider, service=service, base_time=base_time, start=0, end=60
    )

    service.is_active = False
    service.save(update_fields=["is_active"])

    booking.refresh_from_db()
    assert booking.service_id == service.id
