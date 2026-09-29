from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate

from apps.catalog.models import Business, Provider
from apps.scheduling.models import WorkingHours
from apps.scheduling.services.availability import _local_midnight_to_utc

from ..models import Booking

STATS_WINDOW_DAYS = 14


def compute_business_stats(business: Business, now: datetime) -> dict:
    zone = ZoneInfo(business.timezone)
    today = now.astimezone(zone).date()
    window_start_date = today - timedelta(days=STATS_WINDOW_DAYS - 1)
    window_start = _local_midnight_to_utc(window_start_date, zone)
    window_end = _local_midnight_to_utc(today + timedelta(days=1), zone)

    window_bookings = Booking.objects.filter(
        provider__business=business,
        time_range__startswith__gte=window_start,
        time_range__startswith__lt=window_end,
    )

    # One GROUP BY query for all 14 days; zero-count days are filled in below in
    # Python rather than with a second query per day.
    counts_by_day = {
        row["day"]: row["count"]
        for row in (
            window_bookings.annotate(day=TruncDate("time_range__startswith", tzinfo=zone))
            .values("day")
            .annotate(count=Count("id"))
        )
    }
    bookings_per_day = [
        {
            "date": window_start_date + timedelta(days=offset),
            "count": counts_by_day.get(window_start_date + timedelta(days=offset), 0),
        }
        for offset in range(STATS_WINDOW_DAYS)
    ]
    today_bookings_count = counts_by_day.get(today, 0)

    totals = window_bookings.aggregate(
        total=Count("id"),
        cancelled=Count("id", filter=Q(status=Booking.Status.CANCELLED)),
        late_cancellations=Count("id", filter=Q(is_late_cancellation=True)),
    )
    cancellation_rate = (totals["cancelled"] / totals["total"] * 100) if totals["total"] else 0.0

    # Capacity: each weekday occurs exactly twice in any 14-day window, so summing
    # per-weekday interval minutes once and doubling avoids iterating actual dates.
    capacity_minutes: dict[int, int] = defaultdict(int)
    for wh in WorkingHours.objects.filter(provider__business=business, provider__is_active=True):
        minutes = (wh.end_time.hour * 60 + wh.end_time.minute) - (
            wh.start_time.hour * 60 + wh.start_time.minute
        )
        capacity_minutes[wh.provider_id] += minutes * 2

    booked_minutes: dict[int, int] = {
        row["provider_id"]: row["minutes"] or 0
        for row in (
            window_bookings.filter(status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED])
            .values("provider_id")
            .annotate(minutes=Sum("duration_snapshot"))
        )
    }

    providers = Provider.objects.filter(business=business, is_active=True).select_related("user")
    provider_utilization = [
        {
            "provider_id": provider.id,
            "provider_name": provider.user.full_name,
            "utilization_percent": (
                round(booked_minutes.get(provider.id, 0) / capacity_minutes[provider.id] * 100, 1)
                if capacity_minutes.get(provider.id)
                else 0.0
            ),
        }
        for provider in providers
    ]

    return {
        "today_bookings_count": today_bookings_count,
        "bookings_per_day": bookings_per_day,
        "cancellation_rate": round(cancellation_rate, 1),
        "late_cancellation_count": totals["late_cancellations"],
        "provider_utilization": provider_utilization,
    }
