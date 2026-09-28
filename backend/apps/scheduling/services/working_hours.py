from collections import defaultdict
from datetime import time

from django.db import transaction

from apps.catalog.models import Provider
from apps.common.exceptions import DomainError

from ..models import WorkingHours


def validate_no_overlap(intervals: list[tuple[time, time]]) -> None:
    """Raise DomainError if any two (start, end) intervals in the same weekday group overlap.

    Enforced here rather than as a DB exclusion constraint: Postgres has no built-in
    range type for bare `time` values, and this invariant is only ever violated by a
    single admin/provider action (a replace-all PUT), never by concurrent customer
    requests the way double-booking is — so a DB-level constraint isn't proportionate.
    """
    ordered = sorted(intervals, key=lambda interval: interval[0])
    for (_, previous_end), (next_start, _) in zip(ordered, ordered[1:], strict=False):
        if next_start < previous_end:
            raise DomainError(
                "Working hours intervals overlap.",
                code="overlapping_working_hours",
                http_status=400,
            )


def replace_working_hours(provider: Provider, entries: list[dict]) -> list[WorkingHours]:
    by_weekday: dict[int, list[tuple[time, time]]] = defaultdict(list)
    for entry in entries:
        by_weekday[entry["weekday"]].append((entry["start_time"], entry["end_time"]))
    for intervals in by_weekday.values():
        validate_no_overlap(intervals)

    with transaction.atomic():
        WorkingHours.objects.filter(provider=provider).delete()
        WorkingHours.objects.bulk_create(
            [WorkingHours(provider=provider, **entry) for entry in entries]
        )

    return list(WorkingHours.objects.filter(provider=provider))
