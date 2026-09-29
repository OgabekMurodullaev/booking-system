import zoneinfo
from datetime import UTC, datetime, time, timedelta

import pytest
import time_machine
from django.db import connection
from django.test.utils import CaptureQueriesContext
from psycopg.types.range import Range

from apps.bookings.models import Booking
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
URL = "/api/v1/stats/"
FROZEN_NOW = datetime(2026, 6, 15, 8, 0, tzinfo=UTC)  # 2026-06-15 13:00 Tashkent


def _local_dt(hour: int, minute: int = 0) -> datetime:
    today = FROZEN_NOW.astimezone(TASHKENT).date()
    return datetime.combine(today, time(hour, minute), tzinfo=TASHKENT).astimezone(UTC)


def _make_booking(*, customer, provider, service, start_hour, duration, status, **extra):
    start = _local_dt(start_hour)
    end = start + timedelta(minutes=duration)
    defaults = {
        "expires_at": None,
        "submitted_at": start,
        "price_snapshot": service.price,
    }
    defaults.update(extra)
    return Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=Range(start, end),
        blocked_range=Range(start, end),
        status=status,
        duration_snapshot=duration,
        **defaults,
    )


@pytest.fixture
def today_weekday() -> int:
    return FROZEN_NOW.astimezone(TASHKENT).date().weekday()


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_stats_numbers_match_fixture_data(
    admin_client, provider, other_provider, customer, service, today_weekday
):
    WorkingHours.objects.create(
        provider=provider, weekday=today_weekday, start_time=time(9, 0), end_time=time(19, 0)
    )
    WorkingHours.objects.create(
        provider=other_provider, weekday=today_weekday, start_time=time(9, 0), end_time=time(17, 0)
    )

    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=10,
        duration=60,
        status=Booking.Status.CONFIRMED,
    )
    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=11,
        duration=30,
        status=Booking.Status.COMPLETED,
    )
    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=12,
        duration=30,
        status=Booking.Status.PENDING,
        expires_at=FROZEN_NOW + timedelta(hours=1),
    )
    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=13,
        duration=30,
        status=Booking.Status.CANCELLED,
        cancellation_reason="changed mind",
    )
    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=14,
        duration=30,
        status=Booking.Status.CANCELLED,
        is_late_cancellation=True,
        cancellation_reason="too late",
    )

    response = admin_client.get(URL)

    assert response.status_code == 200
    data = response.json()

    assert data["today_bookings_count"] == 5
    assert data["cancellation_rate"] == 40.0
    assert data["late_cancellation_count"] == 1

    today_str = FROZEN_NOW.astimezone(TASHKENT).date().isoformat()
    per_day = {row["date"]: row["count"] for row in data["bookings_per_day"]}
    assert len(data["bookings_per_day"]) == 14
    assert per_day[today_str] == 5
    assert sum(per_day.values()) == 5

    utilization = {
        row["provider_id"]: row["utilization_percent"] for row in data["provider_utilization"]
    }
    assert utilization[provider.id] == 7.5
    assert utilization[other_provider.id] == 0.0


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_non_admin_forbidden(provider_client):
    response = provider_client.get(URL)
    assert response.status_code == 403


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_stats_scoped_to_own_business(
    admin_client, other_admin_client, provider, customer, service, today_weekday
):
    WorkingHours.objects.create(
        provider=provider, weekday=today_weekday, start_time=time(9, 0), end_time=time(17, 0)
    )
    _make_booking(
        customer=customer,
        provider=provider,
        service=service,
        start_hour=10,
        duration=30,
        status=Booking.Status.CONFIRMED,
    )

    other_business_response = other_admin_client.get(URL)

    assert other_business_response.status_code == 200
    assert other_business_response.json()["today_bookings_count"] == 0


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_query_count_constant_regardless_of_booking_volume(
    admin_client, provider, other_provider, customer, service, today_weekday
):
    WorkingHours.objects.create(
        provider=provider, weekday=today_weekday, start_time=time(9, 0), end_time=time(19, 0)
    )

    with CaptureQueriesContext(connection) as few:
        admin_client.get(URL)
    few_count = len(few.captured_queries)

    for hour in range(9, 19):
        _make_booking(
            customer=customer,
            provider=provider,
            service=service,
            start_hour=hour,
            duration=15,
            status=Booking.Status.CONFIRMED,
        )

    with CaptureQueriesContext(connection) as many:
        admin_client.get(URL)
    many_count = len(many.captured_queries)

    assert few_count == many_count
    assert many_count <= 10
