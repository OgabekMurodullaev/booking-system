"""Notification hooks called from apps.bookings.services.booking via transaction.on_commit."""

from apps.bookings.models import Booking

from . import tasks


def notify_hold_created(booking: Booking) -> None:
    pass


def notify_pending_approval(booking: Booking) -> None:
    tasks.send_booking_pending_approval.delay(booking.id)


def notify_booking_confirmed(booking: Booking) -> None:
    tasks.send_booking_confirmed.delay(booking.id)


def notify_booking_cancelled(booking: Booking) -> None:
    tasks.send_booking_cancelled.delay(booking.id)


def notify_booking_completed(booking: Booking) -> None:
    pass
