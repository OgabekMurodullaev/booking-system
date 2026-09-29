import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from django.core import mail
from django.db import transaction
from icalendar import Calendar

from apps.bookings.models import Booking
from apps.bookings.services.booking import (
    cancel_booking,
    confirm_booking,
    create_hold,
    submit_booking,
)
from apps.notifications.tasks import scan_and_send_reminders_task
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
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


@pytest.fixture
def business(business):
    business.auto_confirm = False
    business.save(update_fields=["auto_confirm"])
    return business


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_submit_notifies_provider_of_pending_approval(
    provider, service, working_hours, test_date, customer, business
):
    provider.user.timezone = "Asia/Tashkent"
    provider.user.save(update_fields=["timezone"])

    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    submit_booking(booking, actor=customer)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [provider.user.email]
    assert "10:00" in email.body


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_confirm_notifies_customer_with_parseable_ics(
    provider, service, working_hours, test_date, customer
):
    customer.timezone = "Asia/Tashkent"
    customer.save(update_fields=["timezone"])

    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    submit_booking(booking, actor=customer)
    mail.outbox.clear()

    confirm_booking(booking, actor=provider.user)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [customer.email]
    assert "10:00" in email.body

    assert len(email.attachments) == 1
    filename, content, mimetype = email.attachments[0]
    assert mimetype == "text/calendar"
    calendar = Calendar.from_ical(content)
    assert str(calendar.get("method")) == "REQUEST"
    event = next(iter(calendar.walk("VEVENT")))
    assert str(event["uid"]) == f"booking-{booking.id}@bookingsystem"


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_cancel_notifies_customer_with_cancel_method_same_uid(
    provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    submit_booking(booking, actor=customer)
    confirm_booking(booking, actor=provider.user)
    mail.outbox.clear()

    cancel_booking(booking, actor=customer, reason="changed my mind")

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [customer.email]

    filename, content, mimetype = email.attachments[0]
    calendar = Calendar.from_ical(content)
    assert str(calendar.get("method")) == "CANCEL"
    event = next(iter(calendar.walk("VEVENT")))
    assert str(event["uid"]) == f"booking-{booking.id}@bookingsystem"


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_rolled_back_transition_sends_no_email(
    provider, service, working_hours, test_date, customer
):
    booking = create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    ).booking
    submit_booking(booking, actor=customer)
    mail.outbox.clear()

    class Boom(Exception):
        pass

    with pytest.raises(Boom), transaction.atomic():
        confirm_booking(booking, actor=provider.user)
        raise Boom

    assert mail.outbox == []
    booking.refresh_from_db()
    assert booking.status == Booking.Status.PENDING


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_reminder_sent_once_even_if_scan_runs_twice(
    provider, service, working_hours, test_date, customer
):
    start = _local_dt(test_date, 10, 0)
    booking = create_hold(
        customer=customer, service=service, start=start, provider=provider
    ).booking
    submit_booking(booking, actor=customer)
    confirm_booking(booking, actor=provider.user)
    mail.outbox.clear()

    reminder_time = start - timedelta(hours=24, minutes=5)
    with time_machine.travel(reminder_time):
        first_count = scan_and_send_reminders_task()
        second_count = scan_and_send_reminders_task()

    assert first_count == 1
    assert second_count == 0
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]

    booking.refresh_from_db()
    assert booking.reminder_sent_at is not None


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_reminder_not_sent_outside_the_24h_window(
    provider, service, working_hours, test_date, customer
):
    start = _local_dt(test_date, 10, 0)
    booking = create_hold(
        customer=customer, service=service, start=start, provider=provider
    ).booking
    submit_booking(booking, actor=customer)
    confirm_booking(booking, actor=provider.user)
    mail.outbox.clear()

    far_from_window = start - timedelta(hours=48)
    with time_machine.travel(far_from_window):
        count = scan_and_send_reminders_task()

    assert count == 0
    assert mail.outbox == []
