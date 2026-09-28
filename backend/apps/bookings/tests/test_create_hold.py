import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.conf import settings

from apps.bookings.models import Booking
from apps.bookings.services.booking import create_hold
from apps.common.exceptions import DomainError
from apps.scheduling.models import WorkingHours
from apps.scheduling.services.availability import _local_to_utc

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
def test_happy_path_creates_pending_hold(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)

    result = create_hold(
        customer=customer, service=service, start=start, provider=provider, now=now
    )

    assert result.created is True
    booking = result.booking
    assert booking.status == Booking.Status.PENDING
    assert booking.expires_at == now + timedelta(minutes=settings.BOOKING_HOLD_TTL_MINUTES)
    assert booking.price_snapshot == service.price
    assert booking.duration_snapshot == service.duration_minutes
    assert booking.time_range.lower == start
    assert booking.status_logs.count() == 1
    assert booking.status_logs.first().to_status == Booking.Status.PENDING


@pytest.mark.django_db
def test_not_on_grid_rejected(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_to_utc(test_date, time(10, 7), TASHKENT)

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=customer, service=service, start=start, provider=provider, now=now)
    assert exc_info.value.code == "not_on_grid"
    assert exc_info.value.http_status == 400


@pytest.mark.django_db
def test_outside_booking_window_rejected(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date, 9, 0)
    start = now + timedelta(minutes=15)  # grid-aligned but less than min lead (60 min default)

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=customer, service=service, start=start, provider=provider, now=now)
    assert exc_info.value.code == "outside_booking_window"


@pytest.mark.django_db
def test_outside_working_hours_rejected(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 20, 0)  # after 18:00 close

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=customer, service=service, start=start, provider=provider, now=now)
    assert exc_info.value.code == "outside_working_hours"


@pytest.mark.django_db
def test_provider_on_time_off_rejected(provider, service, customer, working_hours, test_date):
    from apps.scheduling.models import TimeOff

    TimeOff.objects.create(
        provider=provider, start=_local_dt(test_date, 9, 0), end=_local_dt(test_date, 18, 0)
    )
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=customer, service=service, start=start, provider=provider, now=now)
    assert exc_info.value.code == "provider_on_time_off"


@pytest.mark.django_db
def test_provider_conflict_returns_409_with_alternatives(
    provider, service, customer, other_customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)
    create_hold(customer=customer, service=service, start=start, provider=provider, now=now)

    with pytest.raises(DomainError) as exc_info:
        create_hold(
            customer=other_customer, service=service, start=start, provider=provider, now=now
        )
    assert exc_info.value.code == "slot_unavailable"
    assert exc_info.value.http_status == 409
    alternatives = exc_info.value.details["alternatives"]
    assert 0 < len(alternatives) <= 3


@pytest.mark.django_db
def test_customer_self_overlap_returns_409_without_needing_alternatives(
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
    start = _local_dt(test_date, 10, 0)
    create_hold(customer=customer, service=service, start=start, provider=provider, now=now)

    with pytest.raises(DomainError) as exc_info:
        create_hold(
            customer=customer, service=service, start=start, provider=other_provider, now=now
        )
    assert exc_info.value.code == "customer_overlap"
    assert exc_info.value.http_status == 409
