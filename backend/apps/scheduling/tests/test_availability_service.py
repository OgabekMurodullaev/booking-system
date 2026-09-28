import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
from psycopg.types.range import Range

from apps.bookings.models import Booking
from apps.scheduling.models import TimeOff, WorkingHours
from apps.scheduling.services.availability import _local_to_utc, get_available_slots

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
BERLIN = zoneinfo.ZoneInfo("Europe/Berlin")


def _local_dt(d: date, h: int, m: int, zone: zoneinfo.ZoneInfo = TASHKENT) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=zone).astimezone(UTC)


@pytest.fixture
def test_date() -> date:
    return date(2026, 10, 5)


@pytest.fixture
def provider(provider, service):
    """Shadow the shared `provider` fixture so it always offers `service` here."""
    provider.services.add(service)
    return provider


@pytest.mark.django_db
def test_simple_day_no_bookings(provider, service, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 60
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    assert slots[0].start == _local_dt(test_date, 9, 0)
    assert slots[0].end == _local_dt(test_date, 10, 0)
    assert slots[0].provider_ids == [provider.id]
    assert slots[-1].start == _local_dt(test_date, 17, 0)
    assert slots[-1].end == _local_dt(test_date, 18, 0)


@pytest.mark.django_db
def test_lunch_break_no_slot_spans_it(provider, service, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(13, 0)
    )
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(14, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    lunch_start = _local_dt(test_date, 13, 0)
    lunch_end = _local_dt(test_date, 14, 0)
    assert all(slot.end <= lunch_start or slot.start >= lunch_end for slot in slots)
    assert len(slots) > 0


@pytest.mark.django_db
def test_service_and_buffer_overflow_excludes_last_slot(provider, service, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 60
    service.buffer_minutes = 15
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    starts = [slot.start for slot in slots]
    # 17:00 + 60min + 15min buffer = 18:15, overflows the 18:00 close -> excluded.
    assert _local_dt(test_date, 17, 0) not in starts
    # 16:45 + 60min + 15min buffer = 18:00 exactly fits -> included, and is the last slot.
    assert slots[-1].start == _local_dt(test_date, 16, 45)


@pytest.mark.django_db
def test_confirmed_booking_excludes_overlapping_slot(provider, service, customer, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(12, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    booked_start = _local_dt(test_date, 9, 30)
    booked_end = _local_dt(test_date, 10, 0)
    Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=Range(booked_start, booked_end),
        blocked_range=Range(booked_start, booked_end),
        status="confirmed",
        price_snapshot="10.00",
        duration_snapshot=30,
    )
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    starts = [slot.start for slot in slots]
    assert booked_start not in starts
    assert _local_dt(test_date, 9, 0) in starts


@pytest.mark.django_db
def test_time_off_excludes_overlapping_slot(provider, service, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(12, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    TimeOff.objects.create(
        provider=provider, start=_local_dt(test_date, 9, 30), end=_local_dt(test_date, 10, 30)
    )
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    starts = [slot.start for slot in slots]
    assert _local_dt(test_date, 9, 30) not in starts
    assert _local_dt(test_date, 10, 0) not in starts
    assert _local_dt(test_date, 9, 0) in starts
    assert _local_dt(test_date, 10, 30) in starts


@pytest.mark.django_db
def test_expired_pending_booking_does_not_block(provider, service, customer, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(12, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    slot_start = _local_dt(test_date, 9, 0)
    slot_end = _local_dt(test_date, 9, 30)
    now = _local_dt(test_date - timedelta(days=1), 0, 0)
    Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=Range(slot_start, slot_end),
        blocked_range=Range(slot_start, slot_end),
        status="pending",
        expires_at=now - timedelta(minutes=1),
        price_snapshot="10.00",
        duration_snapshot=30,
    )

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    assert slot_start in [slot.start for slot in slots]


@pytest.mark.django_db
def test_cancelled_booking_does_not_block(provider, service, customer, test_date):
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(12, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    slot_start = _local_dt(test_date, 9, 0)
    slot_end = _local_dt(test_date, 9, 30)
    Booking.objects.create(
        customer=customer,
        provider=provider,
        service=service,
        time_range=Range(slot_start, slot_end),
        blocked_range=Range(slot_start, slot_end),
        status="cancelled",
        price_snapshot="10.00",
        duration_snapshot=30,
    )
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    assert slot_start in [slot.start for slot in slots]


@pytest.mark.django_db
def test_min_lead_time_respected(provider, service, test_date):
    WorkingHours.objects.create(
        provider=provider, weekday=test_date.weekday(), start_time=time(9, 0), end_time=time(18, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date, 8, 30)  # default min lead = 60 min -> earliest is 09:30

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    starts = [slot.start for slot in slots]
    assert _local_dt(test_date, 9, 0) not in starts
    assert _local_dt(test_date, 9, 30) in starts


@pytest.mark.django_db
def test_max_advance_respected(provider, service):
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(date(2026, 1, 1), 0, 0)
    within_advance = date(2026, 1, 1) + timedelta(days=20)  # default max advance = 30 days
    beyond_advance = date(2026, 1, 1) + timedelta(days=40)
    for d in (within_advance, beyond_advance):
        WorkingHours.objects.create(
            provider=provider, weekday=d.weekday(), start_time=time(9, 0), end_time=time(10, 0)
        )

    slots_within = get_available_slots(
        service=service,
        date_from=within_advance,
        date_to=within_advance,
        provider=provider,
        now=now,
    )
    slots_beyond = get_available_slots(
        service=service,
        date_from=beyond_advance,
        date_to=beyond_advance,
        provider=provider,
        now=now,
    )

    assert len(slots_within) > 0
    assert slots_beyond == []


@pytest.mark.django_db
def test_two_providers_merge_into_one_slot_with_both_ids(
    provider, other_provider, service, test_date
):
    other_provider.services.add(service)
    weekday = test_date.weekday()
    WorkingHours.objects.create(
        provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(10, 0)
    )
    WorkingHours.objects.create(
        provider=other_provider, weekday=weekday, start_time=time(9, 0), end_time=time(10, 0)
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=None, now=now
    )

    first = next(slot for slot in slots if slot.start == _local_dt(test_date, 9, 0))
    assert sorted(first.provider_ids) == sorted([provider.id, other_provider.id])


@pytest.mark.django_db
def test_inactive_provider_yields_no_slots(provider, service, test_date):
    provider.is_active = False
    provider.save()
    WorkingHours.objects.create(
        provider=provider, weekday=test_date.weekday(), start_time=time(9, 0), end_time=time(18, 0)
    )
    now = _local_dt(test_date - timedelta(days=1), 0, 0)

    slots = get_available_slots(
        service=service, date_from=test_date, date_to=test_date, provider=provider, now=now
    )

    assert slots == []


@pytest.mark.django_db
def test_dst_spring_forward_skips_gap_and_round_trips(provider, service):
    provider.business.timezone = "Europe/Berlin"
    provider.business.save()
    spring_forward_date = date(2026, 3, 29)  # Europe/Berlin: 02:00 -> 03:00 skipped
    WorkingHours.objects.create(
        provider=provider,
        weekday=spring_forward_date.weekday(),
        start_time=time(1, 0),
        end_time=time(4, 0),
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(spring_forward_date - timedelta(days=1), 0, 0, zone=BERLIN)

    slots = get_available_slots(
        service=service,
        date_from=spring_forward_date,
        date_to=spring_forward_date,
        provider=provider,
        now=now,
    )

    assert len(slots) > 0
    for slot in slots:
        local_start = slot.start.astimezone(BERLIN)
        # No slot may start inside the nonexistent 02:00-02:59 wall-clock hour.
        assert local_start.hour != 2
        # Every returned start must round-trip through the same conversion used to
        # detect gaps in the first place (guards against silently-wrong UTC values).
        assert _local_to_utc(local_start.date(), local_start.time(), BERLIN) == slot.start

    expected_before_gap = _local_to_utc(spring_forward_date, time(1, 45), BERLIN)
    expected_after_gap = _local_to_utc(spring_forward_date, time(3, 0), BERLIN)
    starts = {slot.start for slot in slots}
    assert expected_before_gap in starts
    assert expected_after_gap in starts


@pytest.mark.django_db
def test_dst_fall_back_uses_first_occurrence_only(provider, service):
    provider.business.timezone = "Europe/Berlin"
    provider.business.save()
    fall_back_date = date(2026, 10, 25)  # Europe/Berlin: 03:00 -> 02:00, 02:00-02:59 repeats
    WorkingHours.objects.create(
        provider=provider,
        weekday=fall_back_date.weekday(),
        start_time=time(1, 0),
        end_time=time(4, 0),
    )
    service.duration_minutes = 30
    service.buffer_minutes = 0
    service.save()
    now = _local_dt(fall_back_date - timedelta(days=1), 0, 0, zone=BERLIN)

    slots = get_available_slots(
        service=service,
        date_from=fall_back_date,
        date_to=fall_back_date,
        provider=provider,
        now=now,
    )

    local_starts = [slot.start.astimezone(BERLIN) for slot in slots]
    hour_two_labels = [(ls.hour, ls.minute) for ls in local_starts if ls.hour == 2]
    # fold=0 policy: each ambiguous local label (02:00, 02:15, ...) is only ever
    # generated once, never twice for the two real occurrences of that wall-clock hour.
    assert len(hour_two_labels) == len(set(hour_two_labels))
    assert len(hour_two_labels) > 0
