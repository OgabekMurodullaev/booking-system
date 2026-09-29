import zoneinfo
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
import time_machine

from apps.bookings.models import Booking
from apps.bookings.services.booking import confirm_booking, create_hold, submit_booking
from apps.conftest import auth_client
from apps.scheduling.models import TimeOff, WorkingHours

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
def test_time_off_over_confirmed_booking_flags_but_does_not_cancel(
    admin_client, provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    booking = submit_booking(booking, actor=customer)
    booking = confirm_booking(booking, actor=provider.user)

    unaffected = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 14, 0), provider=provider
    ).booking
    submit_booking(unaffected, actor=customer)

    TimeOff.objects.create(
        provider=provider,
        start=_local_dt(test_date, 9, 30),
        end=_local_dt(test_date, 11, 0),
        reason="Sick leave",
    )

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED

    response = admin_client.get(URL)
    results = {row["id"]: row for row in response.json()["results"]}
    assert results[booking.id]["has_time_off_conflict"] is True
    assert results[unaffected.id]["has_time_off_conflict"] is False


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_booking_snapshots_are_immutable_after_service_changes(
    provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    booking.refresh_from_db()
    original_price = booking.price_snapshot
    original_duration = booking.duration_snapshot

    service.price = original_price + Decimal("100")
    service.duration_minutes = original_duration + 15
    service.save(update_fields=["price", "duration_minutes"])

    booking.refresh_from_db()
    assert booking.price_snapshot == original_price
    assert booking.duration_snapshot == original_duration


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_deactivating_service_does_not_affect_existing_booking(
    provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    submit_booking(booking, actor=customer)

    service.is_active = False
    service.save(update_fields=["is_active"])

    client = auth_client(customer)
    response = client.get(f"{URL}{booking.id}/")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    create_response = client.post(
        URL,
        {
            "service": service.id,
            "provider": provider.id,
            "start": _local_dt(test_date, 14, 0).isoformat(),
        },
        format="json",
    )
    assert create_response.status_code == 404
    assert create_response.json()["error"]["code"] == "service_not_found"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_customer_timezone_change_does_not_touch_stored_booking_time(
    provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    original_lower = booking.time_range.lower
    original_upper = booking.time_range.upper

    customer.timezone = "America/New_York"
    customer.save(update_fields=["timezone"])

    booking.refresh_from_db()
    assert booking.time_range.lower == original_lower
    assert booking.time_range.upper == original_upper
