import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.accounts.models import User
from apps.bookings.services.booking import create_hold
from apps.catalog.models import Provider
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
def other_provider(other_provider, service):
    other_provider.services.add(service)
    return other_provider


@pytest.fixture
def working_hours(provider, other_provider, test_date):
    for p in (provider, other_provider):
        WorkingHours.objects.create(
            provider=p, weekday=test_date.weekday(), start_time=time(9, 0), end_time=time(18, 0)
        )


@pytest.mark.django_db
def test_picks_provider_with_fewest_active_bookings_that_day(
    provider, other_provider, service, customer, other_customer, working_hours, test_date, business
):
    now = _local_dt(test_date - timedelta(days=1))

    # Give `provider` one more booking earlier that day than `other_provider`.
    create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 9, 0),
        provider=provider,
        now=now,
    )

    result = create_hold(
        customer=other_customer, service=service, start=_local_dt(test_date, 11, 0), now=now
    )

    assert result.booking.provider_id == other_provider.id


@pytest.mark.django_db
def test_tie_broken_by_id(provider, other_provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    lower_id_provider = min(provider, other_provider, key=lambda p: p.id)

    result = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), now=now
    )

    assert result.booking.provider_id == lower_id_provider.id


@pytest.mark.django_db
def test_all_candidates_conflict_returns_409_with_alternatives(
    provider, other_provider, service, customer, other_customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    start = _local_dt(test_date, 10, 0)
    create_hold(customer=customer, service=service, start=start, provider=provider, now=now)
    create_hold(
        customer=other_customer, service=service, start=start, provider=other_provider, now=now
    )

    third_customer = User.objects.create_user(
        email="third@example.com", password="a-very-strong-pass-123", full_name="Third"
    )

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=third_customer, service=service, start=start, now=now)
    assert exc_info.value.code == "slot_unavailable"
    assert exc_info.value.http_status == 409
    assert len(exc_info.value.details["alternatives"]) > 0


@pytest.mark.django_db
def test_no_active_provider_offers_service_returns_409(service, customer, test_date):
    Provider.objects.filter(services=service).delete()
    now = _local_dt(test_date - timedelta(days=1))

    with pytest.raises(DomainError) as exc_info:
        create_hold(customer=customer, service=service, start=_local_dt(test_date, 10, 0), now=now)
    assert exc_info.value.code == "slot_unavailable"
