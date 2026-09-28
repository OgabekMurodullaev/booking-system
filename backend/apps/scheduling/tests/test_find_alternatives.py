import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.test import override_settings
from psycopg.types.range import Range

from apps.bookings.models import Booking
from apps.scheduling.models import WorkingHours
from apps.scheduling.services.availability import find_alternatives

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")


def _local_dt(d: date, h: int, m: int) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=TASHKENT).astimezone(UTC)


@pytest.fixture
def test_date() -> date:
    return date(2026, 10, 5)


@pytest.fixture
def provider(provider, service):
    provider.services.add(service)
    return provider


@pytest.mark.django_db
def test_returns_up_to_limit_slots_all_after_around(provider, service, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)
    around = _local_dt(test_date, 12, 0)

    alternatives = find_alternatives(service=service, around=around, limit=3, now=now)

    assert len(alternatives) == 3
    assert all(slot.start >= around for slot in alternatives)
    assert alternatives == sorted(alternatives, key=lambda slot: slot.start)


@pytest.mark.django_db
def test_respects_provider_filter(provider, other_provider, service, test_date):
    other_provider.services.add(service)
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
    )
    WorkingHours.objects.create(
        provider=other_provider, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)
    around = _local_dt(test_date, 9, 0)

    alternatives = find_alternatives(
        service=service, around=around, provider=provider, limit=3, now=now
    )

    assert len(alternatives) == 3
    assert all(slot.provider_ids == [provider.id] for slot in alternatives)


@pytest.mark.django_db
@override_settings(BOOKING_MAX_ADVANCE_DAYS=5)
def test_returns_fewer_than_limit_when_scarce(provider, service, test_date):
    # WorkingHours recur weekly, so with a 5-day max-advance horizon only the very
    # first occurrence (test_date itself) falls within the search window at all.
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(9, 30)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)
    around = _local_dt(test_date, 0, 0)

    alternatives = find_alternatives(service=service, around=around, limit=3, now=now)

    assert 0 < len(alternatives) < 3


@pytest.mark.django_db
def test_returned_slots_are_genuinely_free(provider, service, customer, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(10, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    booked_start = _local_dt(test_date, 9, 0)
    booked_end = _local_dt(test_date, 9, 30)
    Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=Range(booked_start, booked_end),
        blocked_range=Range(booked_start, booked_end),
        status="confirmed",
        price_snapshot="10.00",
        duration_snapshot=30,
    )
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    alternatives = find_alternatives(service=service, around=booked_start, limit=3, now=now)

    assert booked_start not in [slot.start for slot in alternatives]
