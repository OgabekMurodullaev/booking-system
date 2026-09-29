from icalendar import Calendar, Event

from apps.bookings.models import Booking


def build_ics(booking: Booking, method: str) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//Booking System//bookings//EN")
    calendar.add("version", "2.0")
    calendar.add("method", method)

    event = Event()
    event.add("uid", f"booking-{booking.id}@bookingsystem")
    event.add("summary", booking.service.name)
    event.add("dtstart", booking.time_range.lower)
    event.add("dtend", booking.time_range.upper)
    event.add("dtstamp", booking.updated_at)
    event.add("status", "CANCELLED" if method == "CANCEL" else "CONFIRMED")
    event.add("sequence", 1 if method == "CANCEL" else 0)
    calendar.add_component(event)

    return calendar.to_ical()
