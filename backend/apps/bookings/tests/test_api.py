import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from rest_framework.test import APIClient

from apps.conftest import auth_client
from apps.scheduling.models import WorkingHours

TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")
URL = "/api/v1/bookings/"
FROZEN_NOW = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


def _local_dt(d: date, h: int = 0, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=TASHKENT).astimezone(UTC)


def _detail_url(pk: int) -> str:
    return f"{URL}{pk}/"


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


@pytest.fixture
def customer_client(customer) -> APIClient:
    return auth_client(customer)


@pytest.fixture
def provider_user_client(provider) -> APIClient:
    return auth_client(provider.user)


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_full_flow_through_http(
    customer_client: APIClient,
    provider_user_client: APIClient,
    provider,
    service,
    working_hours,
    test_date,
):
    start = _local_dt(test_date, 10, 0)

    create_response = customer_client.post(
        URL,
        {"service": service.id, "provider": provider.id, "start": start.isoformat()},
        format="json",
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending"

    submit_response = customer_client.post(f"{URL}{booking_id}/submit/")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "pending"

    confirm_response = provider_user_client.post(f"{URL}{booking_id}/confirm/")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"

    cancel_response = provider_user_client.post(
        f"{URL}{booking_id}/cancel/", {"reason": "provider unavailable"}, format="json"
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_role_scoped_list_customer_sees_only_own(
    customer_client: APIClient,
    provider,
    service,
    working_hours,
    test_date,
    customer,
    other_customer,
):
    from apps.bookings.services.booking import create_hold

    create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    )
    create_hold(
        customer=other_customer,
        service=service,
        start=_local_dt(test_date, 12, 0),
        provider=provider,
    )

    response = customer_client.get(URL)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["customer"] == customer.id


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_role_scoped_list_provider_sees_own_schedule(
    provider_user_client: APIClient,
    provider,
    other_provider,
    service,
    working_hours,
    test_date,
    customer,
):
    from apps.bookings.services.booking import create_hold

    other_provider.services.add(service)
    WorkingHours.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    )
    create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 13, 0),
        provider=other_provider,
    )

    response = provider_user_client.get(URL)

    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["provider"] == provider.id


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_role_scoped_list_admin_sees_whole_business(
    admin_client: APIClient,
    provider,
    other_provider,
    service,
    working_hours,
    test_date,
    customer,
    business,
):
    from apps.bookings.services.booking import create_hold

    other_provider.services.add(service)
    WorkingHours.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    )
    create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 13, 0),
        provider=other_provider,
    )

    response = admin_client.get(URL)

    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_customer_requesting_another_customers_booking_gets_404(
    customer_client: APIClient, provider, service, working_hours, test_date, other_customer
):
    from apps.bookings.services.booking import create_hold

    other_booking = create_hold(
        customer=other_customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
    ).booking

    response = customer_client.get(_detail_url(other_booking.id))

    assert response.status_code == 404


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_detail_includes_status_history(
    customer_client: APIClient, provider, service, working_hours, test_date, customer
):
    from apps.bookings.services.booking import create_hold

    booking = create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 10, 0),
        provider=provider,
    ).booking

    response = customer_client.get(_detail_url(booking.id))

    assert response.status_code == 200
    assert len(response.json()["status_logs"]) == 1


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_filters_narrow_the_list(
    admin_client: APIClient, provider, other_provider, service, working_hours, test_date, customer
):
    from apps.bookings.services.booking import create_hold

    other_provider.services.add(service)
    WorkingHours.objects.create(
        provider=other_provider,
        weekday=test_date.weekday(),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    create_hold(
        customer=customer, service=service, start=_local_dt(test_date, 10, 0), provider=provider
    )
    create_hold(
        customer=customer,
        service=service,
        start=_local_dt(test_date, 13, 0),
        provider=other_provider,
    )

    response = admin_client.get(URL, {"provider": provider.id})

    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["provider"] == provider.id
