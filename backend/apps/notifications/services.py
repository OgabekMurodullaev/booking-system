"""Notification hooks called from apps.bookings.services.booking via transaction.on_commit.

These are intentionally no-ops until Section 7 wires up real Celery tasks (email, .ics,
reminders). Keeping the call sites and function names stable now means Section 7 only
needs to fill in bodies here, not touch the booking service.
"""

from apps.bookings.models import Booking


def notify_hold_created(booking: Booking) -> None:
    pass


def notify_pending_approval(booking: Booking) -> None:
    pass


def notify_booking_confirmed(booking: Booking) -> None:
    pass


def notify_booking_cancelled(booking: Booking) -> None:
    pass


def notify_booking_completed(booking: Booking) -> None:
    pass
