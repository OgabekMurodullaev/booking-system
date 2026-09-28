import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.bookings.models import Booking
from apps.bookings.services.booking import create_hold
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")


def _local_dt(d: date, h: int = 0, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=TASHKENT).astimezone(UTC)


@pytest.fixture
def test_date() -> date:
    return date(2026, 10, 5)


@pytest.fixture
def provider(provider, service):
    provider.services.add(service)
    return provider


@pytest.fixture
def working_hours(provider, test_date):
    WorkingHours.objects.create(
        provider=provider, weekday=test_date.weekday(), start_time=time(9, 0), end_time=time(18, 0)
    )


@pytest.mark.django_db
def test_replay_with_same_key_returns_same_booking_no_duplicate(
    provider, service, customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)

    first = create_hold(
        customer=customer,
        service=service,
        start=start,
        provider=provider,
        idempotency_key="key-1",
        now=now,
    )
    second = create_hold(
        customer=customer,
        service=service,
        start=start,
        provider=provider,
        idempotency_key="key-1",
        now=now,
    )

    assert first.created is True
    assert second.created is False
    assert first.booking.id == second.booking.id
    assert Booking.objects.filter(customer=customer).count() == 1


@pytest.mark.django_db
def test_replay_ignores_changed_params(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)
    other_start = _local_dt(test_date, 11, 0)

    first = create_hold(
        customer=customer,
        service=service,
        start=start,
        provider=provider,
        idempotency_key="key-2",
        now=now,
    )
    # Same key but a different requested start -> still returns the original hold.
    second = create_hold(
        customer=customer,
        service=service,
        start=other_start,
        provider=provider,
        idempotency_key="key-2",
        now=now,
    )

    assert second.created is False
    assert second.booking.id == first.booking.id
    assert second.booking.time_range.lower == start


@pytest.mark.django_db
def test_no_key_creates_independent_holds(
    provider, other_provider, service, customer, working_hours, test_date
):
    other_provider.services.add(service)
    WorkingHours.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    now = _local_dt(test_date - timedelta(days=1))

    first = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        now=now,
    )
    second = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 13, 0),
        provider=other_provider,
        now=now,
    )

    assert first.created is True
    assert second.created is True
    assert first.booking.id != second.booking.id


@pytest.mark.django_db
def test_different_key_creates_new_hold(
    provider, other_provider, service, customer, working_hours, test_date
):
    other_provider.services.add(service)
    WorkingHours.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    now = _local_dt(test_date - timedelta(days=1))

    first = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        idempotency_key="key-a",
        now=now,
    )
    second = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 13, 0),
        provider=other_provider,
        idempotency_key="key-b",
        now=now,
    )

    assert first.created is True
    assert second.created is True
    assert Booking.objects.filter(customer=customer).count() == 2
