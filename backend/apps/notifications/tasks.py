import zoneinfo
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking

from .ics import build_ics

_RETRY_KWARGS = {"autoretry_for": (Exception,), "retry_backoff": True, "max_retries": 5}


def _local(dt, tz_name: str) -> str:
    return dt.astimezone(zoneinfo.ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")


def _send(
    booking: Booking, recipient: User, template: str, subject: str, ics_method: str | None = None
) -> None:
    context = {
        "recipient_name": recipient.full_name,
        "customer_name": booking.customer.full_name,
        "provider_name": booking.provider.user.full_name,
        "service_name": booking.service.name,
        "start_local": _local(booking.time_range.lower, recipient.timezone),
        "end_local": _local(booking.time_range.upper, recipient.timezone),
        "timezone_name": recipient.timezone,
        "cancellation_reason": booking.cancellation_reason,
    }
    text_body = render_to_string(f"notifications/{template}.txt", context)
    html_body = render_to_string(f"notifications/{template}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email],
    )
    message.attach_alternative(html_body, "text/html")
    if ics_method is not None:
        message.attach("booking.ics", build_ics(booking, method=ics_method), "text/calendar")
    message.send()


def _load_booking(booking_id: int) -> Booking:
    return Booking.objects.select_related("customer", "provider__user", "service").get(
        pk=booking_id
    )


@shared_task(bind=True, **_RETRY_KWARGS)
def send_booking_confirmed(self, booking_id: int) -> None:
    booking = _load_booking(booking_id)
    _send(
        booking,
        recipient=booking.customer,
        template="booking_confirmed",
        subject="Your booking is confirmed",
        ics_method="REQUEST",
    )


@shared_task(bind=True, **_RETRY_KWARGS)
def send_booking_cancelled(self, booking_id: int) -> None:
    booking = _load_booking(booking_id)
    _send(
        booking,
        recipient=booking.customer,
        template="booking_cancelled",
        subject="Your booking has been cancelled",
        ics_method="CANCEL",
    )


@shared_task(bind=True, **_RETRY_KWARGS)
def send_booking_pending_approval(self, booking_id: int) -> None:
    booking = _load_booking(booking_id)
    _send(
        booking,
        recipient=booking.provider.user,
        template="booking_pending_approval",
        subject="A booking needs your approval",
    )


@shared_task(bind=True, **_RETRY_KWARGS)
def send_booking_reminder(self, booking_id: int) -> None:
    booking = _load_booking(booking_id)
    _send(
        booking,
        recipient=booking.customer,
        template="booking_reminder",
        subject="Reminder: upcoming booking",
    )


@shared_task
def scan_and_send_reminders_task() -> int:
    now = timezone.now()
    window_start = now + timedelta(hours=24)
    window_end = now + timedelta(hours=24, minutes=15)

    candidate_ids = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        reminder_sent_at__isnull=True,
        time_range__startswith__gte=window_start,
        time_range__startswith__lt=window_end,
    ).values_list("id", flat=True)

    sent = 0
    for booking_id in candidate_ids:
        claimed = Booking.objects.filter(pk=booking_id, reminder_sent_at__isnull=True).update(
            reminder_sent_at=now
        )
        if claimed:
            send_booking_reminder.delay(booking_id)
            sent += 1
    return sent
