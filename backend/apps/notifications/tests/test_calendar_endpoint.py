import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from icalendar import Calendar

from apps.bookings.services.booking import create_hold
from apps.conftest import auth_client
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
URL = "/api/v1/bookings/"
FROZEN_NOW = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


def _local_dt(d: date, h: int = 0, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=TASHKENT).astimezone(UTC)


@pytest.fixture
def test_date() -> date:
    return FROZEN_NOW.astimezone(TASHKENT).date() + timedelta(days=3)


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
@time_machine.travel(FROZEN_NOW)
def test_owner_can_download_calendar_ics(provider, service, working_hours, test_date, customer):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking

    response = auth_client(customer).get(f"{URL}{booking.id}/calendar.ics")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar"
    calendar = Calendar.from_ical(response.content)
    event = next(iter(calendar.walk("VEVENT")))
    assert str(event["uid"]) == f"booking-{booking.id}@bookingsystem"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_other_customer_cannot_download_someone_elses_calendar(
    provider, service, working_hours, test_date, customer, other_customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking

    response = auth_client(other_customer).get(f"{URL}{booking.id}/calendar.ics")

    assert response.status_code == 404
