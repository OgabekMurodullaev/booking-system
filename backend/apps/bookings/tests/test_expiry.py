import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.bookings.models import Booking
from apps.bookings.services.booking import create_hold, expire_stale_holds, submit_booking
from apps.common.exceptions import DomainError
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
def test_expired_hold_cannot_be_submitted(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    hold = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        now=now,
    ).booking

    after_expiry = hold.expires_at + timedelta(minutes=1)
    with pytest.raises(DomainError) as exc_info:
        submit_booking(hold, actor=customer, now=after_expiry)
    assert exc_info.value.code == "hold_expired"


@pytest.mark.django_db
def test_lazy_expiry_lets_new_customer_book_the_slot(
    provider, service, customer, other_customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)
    first = create_hold(
        customer=customer, service=service, start=start, provider=provider, now=now
    ).booking

    after_expiry = first.expires_at + timedelta(minutes=1)
    # No beat sweep is run here -- the slot must free up purely via create_hold's own
    # lazy expiry of overlapping stale holds for the same provider.
    result = create_hold(
        customer=other_customer, service=service, start=start, provider=provider, now=after_expiry
    )

    assert result.created is True
    first.refresh_from_db()
    assert first.status == Booking.Status.CANCELLED
    assert first.status_logs.filter(reason="expired").exists()


@pytest.mark.django_db
def test_expire_stale_holds_bulk_transitions_all_due_holds(
    provider, other_provider, service, customer, other_customer, working_hours, test_date
):
    from apps.scheduling.models import WorkingHours as WH

    other_provider.services.add(service)
    WH.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    now = _local_dt(test_date - timedelta(days=1))
    hold1 = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        now=now,
    ).booking
    hold2 = create_hold(
        customer=other_customer,
        service=service,
        start=_local_dt(test_date, 11, 0),
        provider=other_provider,
        now=now,
    ).booking

    after_expiry = max(hold1.expires_at, hold2.expires_at) + timedelta(minutes=1)
    count = expire_stale_holds(after_expiry)

    assert count == 2
    hold1.refresh_from_db()
    hold2.refresh_from_db()
    assert hold1.status == Booking.Status.CANCELLED
    assert hold2.status == Booking.Status.CANCELLED
    assert hold1.status_logs.filter(reason="expired").count() == 1
    assert hold2.status_logs.filter(reason="expired").count() == 1


@pytest.mark.django_db
def test_expire_stale_holds_does_not_touch_confirmed_bookings(
    provider, service, customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    hold = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        now=now,
    ).booking
    hold = submit_booking(hold, actor=customer, now=now)
    from apps.bookings.services.booking import confirm_booking

    hold = confirm_booking(hold, actor=provider.user, now=now)

    count = expire_stale_holds(now + timedelta(days=1))

    assert count == 0
    hold.refresh_from_db()
    assert hold.status == Booking.Status.CONFIRMED
