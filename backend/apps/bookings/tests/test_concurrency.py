import threading
import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from django.db import connections

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.bookings.services.booking import (
    STATE_MACHINE,
    cancel_booking,
    confirm_booking,
    create_hold,
    submit_booking,
)
from apps.common.exceptions import DomainError
from apps.conftest import auth_client
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
URL = "/api/v1/bookings/"
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


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_ten_customers_racing_same_slot_exactly_one_succeeds(
    provider, service, working_hours, test_date
):
    start = _local_dt(test_date, 10, 0)
    customers = [
        User.objects.create_user(
            email=f"race{i}@example.com", password="a-very-strong-pass-123", full_name=f"Race {i}"
        )
        for i in range(10)
    ]

    barrier = threading.Barrier(len(customers))
    results = []

    def attempt(customer):
        barrier.wait()
        try:
            client = auth_client(customer)
            response = client.post(
                URL,
                {"service": service.id, "provider": provider.id, "start": start.isoformat()},
                format="json",
            )
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(c,)) for c in customers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == sorted([201] + [409] * 9)
    assert Booking.objects.filter(provider=provider).count() == 1


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_auto_assign_five_requests_three_providers_exactly_three_succeed(
    service, business, test_date
):
    from apps.catalog.models import Provider

    providers = []
    for i in range(3):
        user = User.objects.create_user(
            email=f"autoprov{i}@example.com",
            password="a-very-strong-pass-123",
            full_name=f"Provider {i}",
            role=User.Role.PROVIDER,
            business=business,
        )
        provider = Provider.objects.create(user=user, business=business)
        provider.services.add(service)
        WorkingHours.objects.create(
            provider=provider,
            weekday=test_date.weekday(),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        providers.append(provider)

    start = _local_dt(test_date, 10, 0)
    customers = [
        User.objects.create_user(
            email=f"autocust{i}@example.com",
            password="a-very-strong-pass-123",
            full_name=f"Cust {i}",
        )
        for i in range(5)
    ]

    barrier = threading.Barrier(len(customers))
    results = []

    def attempt(customer):
        barrier.wait()
        try:
            client = auth_client(customer)
            response = client.post(
                URL, {"service": service.id, "start": start.isoformat()}, format="json"
            )
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(c,)) for c in customers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == sorted([201] * 3 + [409] * 2)
    bookings = Booking.objects.filter(provider__in=providers, time_range__startswith=start)
    assert bookings.count() == 3
    assert bookings.values_list("provider_id", flat=True).distinct().count() == 3


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_same_idempotency_key_five_concurrent_requests_exactly_one_booking(
    provider, service, working_hours, test_date, customer
):
    start = _local_dt(test_date, 10, 0)
    barrier = threading.Barrier(5)
    results = []

    def attempt():
        barrier.wait()
        try:
            client = auth_client(customer)
            response = client.post(
                URL,
                {"service": service.id, "provider": provider.id, "start": start.isoformat()},
                format="json",
                HTTP_IDEMPOTENCY_KEY="race-key",
            )
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == sorted([201] + [200] * 4)
    assert Booking.objects.filter(customer=customer).count() == 1


@pytest.mark.django_db(transaction=True)
@time_machine.travel(FROZEN_NOW)
def test_concurrent_confirm_and_cancel_same_booking_is_consistent(
    provider, service, working_hours, test_date, customer
):
    start = _local_dt(test_date, 10, 0)
    booking = create_hold(
        customer=customer, service=service, start=start, provider=provider
    ).booking
    booking = submit_booking(booking, actor=customer)

    barrier = threading.Barrier(2)
    results = {}

    def do_confirm():
        barrier.wait()
        try:
            updated = confirm_booking(booking, actor=provider.user)
            results["confirm"] = updated.status
        except DomainError as exc:
            results["confirm"] = exc.code
        finally:
            connections.close_all()

    def do_cancel():
        barrier.wait()
        try:
            updated = cancel_booking(booking, actor=customer, reason="changed my mind")
            results["cancel"] = updated.status
        except DomainError as exc:
            results["cancel"] = exc.code
        finally:
            connections.close_all()

    threads = [threading.Thread(target=do_confirm), threading.Thread(target=do_cancel)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # select_for_update() serializes the two calls rather than letting them race on a
    # stale read, but it does NOT force exactly one of them to fail: if confirm wins
    # first (pending -> confirmed), the cancel call re-reads the row, sees
    # status=confirmed, and (confirmed -> cancelled) is itself a *valid* edge per the
    # state machine (a customer may cancel an already-confirmed booking) -- so it
    # legitimately succeeds too, as a valid follow-on transition, not a race bug. If
    # cancel wins first instead, confirm's retry correctly gets invalid_transition
    # (confirmed/cancelled has no (cancelled, confirmed) edge). Both outcomes are
    # "consistent" in the sense the acceptance criterion means: no impossible
    # transition is ever logged, and the persisted status always matches the log.
    assert results["confirm"] in (Booking.Status.CONFIRMED, "invalid_transition")
    assert results["cancel"] in (Booking.Status.CANCELLED, "invalid_transition")
    assert not (
        results["confirm"] == "invalid_transition" and results["cancel"] == "invalid_transition"
    )

    booking.refresh_from_db()
    logs = list(booking.status_logs.order_by("created_at"))
    assert [log.to_status for log in logs[:2]] == ["pending", "pending"]
    transition_logs = logs[2:]
    assert 1 <= len(transition_logs) <= 2
    for log in transition_logs:
        assert (log.from_status, log.to_status) in STATE_MACHINE
    assert booking.status == transition_logs[-1].to_status
