from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.utils import timezone as django_timezone
from psycopg.types.range import Range

from apps.bookings.models import Booking
from apps.catalog.models import Provider, Service

from ..models import TimeOff, WorkingHours
from .intervals import Interval, subtract_intervals


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    provider_ids: list[int] = field(default_factory=list)


def _local_to_utc(
    local_date: date, local_time: time, zone: ZoneInfo, *, fold: int = 0
) -> datetime | None:
    """Convert a local wall-clock (date, time) in `zone` to an aware UTC datetime.

    Returns None if the wall-clock time does not exist on that date in that zone
    (a spring-forward DST gap) — zoneinfo does not raise for this, it silently
    normalizes to a real instant, so we detect it via a round-trip comparison.
    `fold` selects which UTC offset to use for an ambiguous (fall-back) local time.
    """
    naive = datetime.combine(local_date, local_time)
    aware = naive.replace(tzinfo=zone, fold=fold)
    utc = aware.astimezone(UTC)
    round_trip = utc.astimezone(zone)
    if (round_trip.year, round_trip.month, round_trip.day, round_trip.hour, round_trip.minute) != (
        local_date.year,
        local_date.month,
        local_date.day,
        local_time.hour,
        local_time.minute,
    ):
        return None
    return utc


def _local_midnight_to_utc(local_date: date, zone: ZoneInfo) -> datetime:
    return _local_to_utc(local_date, time.min, zone) or _local_to_utc(
        local_date, time.min, zone, fold=1
    )


def _grid_starts(start_time: time, end_time: time, step_minutes: int) -> list[time]:
    """Local time-of-day candidates within [start_time, end_time), on a grid aligned
    to `step_minutes` from local midnight (e.g. :00/:15/:30/:45 for a 15-min step)."""
    start_total = start_time.hour * 60 + start_time.minute
    end_total = end_time.hour * 60 + end_time.minute
    first = ((start_total + step_minutes - 1) // step_minutes) * step_minutes
    candidates = []
    total = first
    while total < end_total:
        candidates.append(time(total // 60, total % 60))
        total += step_minutes
    return candidates


def _group_slots_by_time(per_provider_slots: dict[int, list[Interval]]) -> list[Slot]:
    """Combine identical (start, end) slots from different providers into one Slot each.

    This is a grouping/aggregation of already-computed slot results, distinct from
    merge_intervals' interval algebra — see the module docstring in intervals.py.
    """
    grouped: dict[Interval, list[int]] = {}
    for provider_id, slots in per_provider_slots.items():
        for start, end in slots:
            grouped.setdefault((start, end), []).append(provider_id)
    return [
        Slot(start=start, end=end, provider_ids=sorted(ids))
        for (start, end), ids in sorted(grouped.items(), key=lambda item: item[0][0])
    ]


def get_available_slots(
    service: Service,
    date_from: date,
    date_to: date,
    provider: Provider | None = None,
    now: datetime | None = None,
) -> list[Slot]:
    """Compute free booking slots for `service` across [date_from, date_to] (inclusive).

    Deterministic given `now` — never reads the real clock internally.
    """
    if now is None:
        now = django_timezone.now()

    business = service.business
    zone = ZoneInfo(business.timezone)

    providers_qs = Provider.objects.filter(business=business, is_active=True, services=service)
    if provider is not None:
        providers_qs = providers_qs.filter(pk=provider.pk)
    provider_ids = list(providers_qs.values_list("id", flat=True))
    if not provider_ids:
        return []

    window_start = _local_midnight_to_utc(date_from, zone)
    window_end = _local_midnight_to_utc(date_to + timedelta(days=1), zone)

    working_hours_by_provider: dict[int, dict[int, list[tuple[time, time]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for wh in WorkingHours.objects.filter(provider_id__in=provider_ids):
        working_hours_by_provider[wh.provider_id][wh.weekday].append((wh.start_time, wh.end_time))

    time_off_by_provider: dict[int, list[Interval]] = defaultdict(list)
    for entry in TimeOff.objects.filter(
        provider_id__in=provider_ids, start__lt=window_end, end__gt=window_start
    ):
        time_off_by_provider[entry.provider_id].append((entry.start, entry.end))

    active_bookings = (
        Booking.objects.filter(provider_id__in=provider_ids)
        .filter(
            Q(status=Booking.Status.CONFIRMED)
            | Q(status=Booking.Status.PENDING, expires_at__gt=now)
        )
        .filter(blocked_range__overlap=Range(window_start, window_end))
    )
    bookings_by_provider: dict[int, list[Interval]] = defaultdict(list)
    for booking in active_bookings:
        bookings_by_provider[booking.provider_id].append(
            (booking.blocked_range.lower, booking.blocked_range.upper)
        )

    duration = timedelta(minutes=service.duration_minutes)
    buffer = timedelta(minutes=service.buffer_minutes)
    step_minutes = settings.BOOKING_SLOT_STEP_MINUTES
    earliest_start = now + timedelta(minutes=settings.BOOKING_MIN_LEAD_MINUTES)
    latest_start = now + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS)

    day_count = (date_to - date_from).days + 1
    per_provider_slots: dict[int, list[Interval]] = {}

    for provider_id in provider_ids:
        wh_by_weekday = working_hours_by_provider.get(provider_id, {})
        blockers = time_off_by_provider.get(provider_id, []) + bookings_by_provider.get(
            provider_id, []
        )
        slots: list[Interval] = []

        for day_offset in range(day_count):
            local_date = date_from + timedelta(days=day_offset)
            weekday = local_date.weekday()
            day_intervals = wh_by_weekday.get(weekday, [])
            if not day_intervals:
                continue

            working_utc = []
            for start_time, end_time in day_intervals:
                start_utc = _local_to_utc(local_date, start_time, zone)
                end_utc = _local_to_utc(local_date, end_time, zone)
                if start_utc is not None and end_utc is not None:
                    working_utc.append((start_utc, end_utc))
            if not working_utc:
                continue

            free_intervals = subtract_intervals(working_utc, blockers)

            for start_time, end_time in day_intervals:
                for local_candidate in _grid_starts(start_time, end_time, step_minutes):
                    candidate_start = _local_to_utc(local_date, local_candidate, zone)
                    if candidate_start is None:
                        continue
                    if not (earliest_start <= candidate_start <= latest_start):
                        continue
                    candidate_blocked_end = candidate_start + duration + buffer
                    if any(
                        free_start <= candidate_start and candidate_blocked_end <= free_end
                        for free_start, free_end in free_intervals
                    ):
                        slots.append((candidate_start, candidate_start + duration))

        per_provider_slots[provider_id] = slots

    return _group_slots_by_time(per_provider_slots)


def find_alternatives(
    service: Service,
    around: datetime,
    provider: Provider | None = None,
    limit: int = 3,
    now: datetime | None = None,
) -> list[Slot]:
    """Find up to `limit` free slots for `service`, at or after `around` (forward-only)."""
    if now is None:
        now = django_timezone.now()

    zone = ZoneInfo(service.business.timezone)
    window_days = settings.AVAILABILITY_MAX_QUERY_DAYS
    max_advance_date = (
        (now + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS)).astimezone(zone).date()
    )
    search_date = around.astimezone(zone).date()

    found: list[Slot] = []
    max_iterations = 3
    for iteration in range(max_iterations):
        date_from = search_date + timedelta(days=iteration * window_days)
        if date_from > max_advance_date:
            break
        date_to = min(date_from + timedelta(days=window_days - 1), max_advance_date)

        slots = get_available_slots(
            service=service, date_from=date_from, date_to=date_to, provider=provider, now=now
        )
        found.extend(slot for slot in slots if slot.start >= around)
        if len(found) >= limit:
            break

    found.sort(key=lambda slot: slot.start)
    return found[:limit]
