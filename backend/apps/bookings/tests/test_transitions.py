import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.bookings.models import Booking
from apps.bookings.services.booking import (
    cancel_booking,
    complete_booking,
    confirm_booking,
    create_hold,
    submit_booking,
    transition_booking,
)
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


def _hold(provider, service, customer, test_date, now):
    return create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
        now=now,
    ).booking


@pytest.mark.django_db
def test_happy_path_manual_confirm(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)

    booking = submit_booking(booking, actor=customer, now=now)
    assert booking.status == Booking.Status.PENDING
    assert booking.submitted_at == now

    booking = confirm_booking(booking, actor=provider.user, now=now)
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.expires_at is None


@pytest.mark.django_db
def test_happy_path_auto_confirm(provider, service, customer, working_hours, test_date, business):
    business.auto_confirm = True
    business.save()
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)

    booking = submit_booking(booking, actor=customer, now=now)
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.expires_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (Booking.Status.CANCELLED, Booking.Status.CONFIRMED),
        (Booking.Status.COMPLETED, Booking.Status.CONFIRMED),
        (Booking.Status.PENDING, Booking.Status.COMPLETED),
        (Booking.Status.CONFIRMED, Booking.Status.PENDING),
    ],
)
def test_invalid_edges_return_409(
    provider, service, customer, working_hours, test_date, from_status, to_status
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking.status = from_status
    if from_status != Booking.Status.PENDING:
        booking.expires_at = None
    booking.save()

    with pytest.raises(DomainError) as exc_info:
        transition_booking(booking, to_status, actor=provider.user, now=now)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.http_status == 409


@pytest.mark.django_db
def test_wrong_actor_returns_403(
    provider, service, customer, other_customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    submit_booking(booking, actor=customer, now=now)
    booking.refresh_from_db()

    with pytest.raises(DomainError) as exc_info:
        confirm_booking(booking, actor=other_customer, now=now)
    assert exc_info.value.code == "permission_denied"
    assert exc_info.value.http_status == 403


@pytest.mark.django_db
def test_confirming_unsubmitted_pending_returns_409(
    provider, service, customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)

    with pytest.raises(DomainError) as exc_info:
        confirm_booking(booking, actor=provider.user, now=now)
    assert exc_info.value.code == "not_submitted"


@pytest.mark.django_db
def test_confirming_expired_pending_returns_409(
    provider, service, customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    submit_booking(booking, actor=customer, now=now)
    booking.refresh_from_db()

    later = booking.expires_at + timedelta(minutes=1)
    with pytest.raises(DomainError) as exc_info:
        confirm_booking(booking, actor=provider.user, now=later)
    assert exc_info.value.code == "hold_expired"


@pytest.mark.django_db
def test_late_cancellation_flagged(provider, service, customer, working_hours, test_date, business):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)

    within_window = booking.time_range.lower - timedelta(
        hours=business.cancellation_window_hours - 1
    )
    booking = cancel_booking(booking, actor=customer, reason="changed my mind", now=within_window)

    assert booking.status == Booking.Status.CANCELLED
    assert booking.is_late_cancellation is True


@pytest.mark.django_db
def test_non_late_cancellation_not_flagged(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)

    booking = cancel_booking(booking, actor=customer, reason="changed my mind", now=now)

    assert booking.is_late_cancellation is False


@pytest.mark.django_db
def test_provider_cancellation_never_flagged_late(
    provider, service, customer, working_hours, test_date, business
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)

    within_window = booking.time_range.lower - timedelta(minutes=5)
    booking = cancel_booking(booking, actor=provider.user, reason="unavailable", now=within_window)

    assert booking.is_late_cancellation is False


@pytest.mark.django_db
def test_completing_before_end_returns_409(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)

    with pytest.raises(DomainError) as exc_info:
        complete_booking(booking, actor=provider.user, now=now)
    assert exc_info.value.code == "booking_not_yet_ended"


@pytest.mark.django_db
def test_completing_after_end_succeeds(provider, service, customer, working_hours, test_date):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)

    after_end = booking.time_range.upper + timedelta(minutes=1)
    booking = complete_booking(booking, actor=provider.user, now=after_end)

    assert booking.status == Booking.Status.COMPLETED


@pytest.mark.django_db
def test_status_log_has_one_row_per_transition_with_actor(
    provider, service, customer, working_hours, test_date
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)
    booking = confirm_booking(booking, actor=provider.user, now=now)
    booking = cancel_booking(booking, actor=provider.user, reason="closed", now=now)

    logs = list(booking.status_logs.order_by("created_at"))
    assert [(log.from_status, log.to_status, log.actor_id) for log in logs] == [
        ("", "pending", customer.id),
        ("pending", "pending", customer.id),
        ("pending", "confirmed", provider.user.id),
        ("confirmed", "cancelled", provider.user.id),
    ]


@pytest.mark.django_db
def test_admin_can_confirm_and_cancel(
    provider, service, customer, working_hours, test_date, admin_user
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    booking = submit_booking(booking, actor=customer, now=now)

    booking = confirm_booking(booking, actor=admin_user, now=now)
    assert booking.status == Booking.Status.CONFIRMED

    booking = cancel_booking(booking, actor=admin_user, reason="admin action", now=now)
    assert booking.status == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_admin_of_another_business_cannot_confirm(
    provider, service, customer, working_hours, test_date, other_admin_user
):
    now = _local_dt(test_date - timedelta(days=1))
    booking = _hold(provider, service, customer, test_date, now)
    submit_booking(booking, actor=customer, now=now)
    booking.refresh_from_db()

    with pytest.raises(DomainError) as exc_info:
        confirm_booking(booking, actor=other_admin_user, now=now)
    assert exc_info.value.code == "permission_denied"
