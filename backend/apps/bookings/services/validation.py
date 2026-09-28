from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.catalog.models import Business, Provider
from apps.common.exceptions import DomainError
from apps.scheduling.models import TimeOff, WorkingHours
from apps.scheduling.services.availability import _local_to_utc


def validate_grid_alignment(business: Business, start: datetime) -> None:
    zone = ZoneInfo(business.timezone)
    local = start.astimezone(zone)
    step = settings.BOOKING_SLOT_STEP_MINUTES
    total_minutes = local.hour * 60 + local.minute
    if local.second or local.microsecond or total_minutes % step != 0:
        raise DomainError(
            "Start time must align to the booking grid.",
            code="not_on_grid",
            http_status=400,
        )


def validate_lead_and_advance(start: datetime, now: datetime) -> None:
    earliest = now + timedelta(minutes=settings.BOOKING_MIN_LEAD_MINUTES)
    latest = now + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS)
    if start < earliest or start > latest:
        raise DomainError(
            "Start time is outside the allowed booking window.",
            code="outside_booking_window",
            http_status=400,
        )


def validate_working_hours_and_time_off(provider: Provider, start: datetime, end: datetime) -> None:
    zone = ZoneInfo(provider.business.timezone)
    local_date = start.astimezone(zone).date()
    weekday = local_date.weekday()

    inside_working_hours = False
    for working_hours in WorkingHours.objects.filter(provider=provider, weekday=weekday):
        wh_start = _local_to_utc(local_date, working_hours.start_time, zone)
        wh_end = _local_to_utc(local_date, working_hours.end_time, zone)
        if wh_start is not None and wh_end is not None and wh_start <= start and end <= wh_end:
            inside_working_hours = True
            break
    if not inside_working_hours:
        raise DomainError(
            "Start time is outside the provider's working hours.",
            code="outside_working_hours",
            http_status=400,
        )

    if TimeOff.objects.filter(provider=provider, start__lt=end, end__gt=start).exists():
        raise DomainError(
            "Provider is on time off during this period.",
            code="provider_on_time_off",
            http_status=400,
        )
