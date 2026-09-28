import zoneinfo
from datetime import date, datetime, time, timedelta

import pytest

from apps.bookings.services.validation import (
    validate_grid_alignment,
    validate_lead_and_advance,
    validate_working_hours_and_time_off,
)
from apps.common.exceptions import DomainError
from apps.scheduling.models import TimeOff, WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")


def _local_dt(d: date, h: int, m: int) -> datetime:
    from datetime import UTC

    return datetime.combine(d, time(h, m), tzinfo=TASHKENT).astimezone(UTC)


@pytest.mark.django_db
def test_grid_aligned_start_passes(business):
    validate_grid_alignment(business, _local_dt(date(2026, 10, 5), 9, 0))
    validate_grid_alignment(business, _local_dt(date(2026, 10, 5), 9, 15))


@pytest.mark.django_db
def test_non_grid_start_rejected(business):
    with pytest.raises(DomainError) as exc_info:
        validate_grid_alignment(business, _local_dt(date(2026, 10, 5), 9, 7))
    assert exc_info.value.code == "not_on_grid"
    assert exc_info.value.http_status == 400


@pytest.mark.django_db
def test_within_lead_and_advance_window_passes():
    from datetime import UTC

    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    validate_lead_and_advance(now + timedelta(days=2), now)


@pytest.mark.django_db
def test_too_soon_rejected():
    from datetime import UTC

    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    with pytest.raises(DomainError) as exc_info:
        validate_lead_and_advance(now + timedelta(minutes=30), now)
    assert exc_info.value.code == "outside_booking_window"


@pytest.mark.django_db
def test_too_far_ahead_rejected():
    from datetime import UTC

    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    with pytest.raises(DomainError) as exc_info:
        validate_lead_and_advance(now + timedelta(days=31), now)
    assert exc_info.value.code == "outside_booking_window"


@pytest.mark.django_db
def test_inside_working_hours_passes(provider):
    d = date(2026, 10, 5)
    WorkingHours.objects.create(
        provider=provider, weekday=d.weekday(), start_time=time(9, 0), end_time=time(18, 0)
    )
    validate_working_hours_and_time_off(provider, _local_dt(d, 9, 0), _local_dt(d, 9, 30))


@pytest.mark.django_db
def test_outside_working_hours_rejected(provider):
    d = date(2026, 10, 5)
    WorkingHours.objects.create(
        provider=provider, weekday=d.weekday(), start_time=time(9, 0), end_time=time(12, 0)
    )
    with pytest.raises(DomainError) as exc_info:
        validate_working_hours_and_time_off(provider, _local_dt(d, 14, 0), _local_dt(d, 14, 30))
    assert exc_info.value.code == "outside_working_hours"


@pytest.mark.django_db
def test_time_off_rejected(provider):
    d = date(2026, 10, 5)
    WorkingHours.objects.create(
        provider=provider, weekday=d.weekday(), start_time=time(9, 0), end_time=time(18, 0)
    )
    TimeOff.objects.create(provider=provider, start=_local_dt(d, 10, 0), end=_local_dt(d, 12, 0))

    with pytest.raises(DomainError) as exc_info:
        validate_working_hours_and_time_off(provider, _local_dt(d, 10, 30), _local_dt(d, 11, 0))
    assert exc_info.value.code == "provider_on_time_off"
