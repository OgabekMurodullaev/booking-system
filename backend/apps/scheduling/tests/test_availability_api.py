import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.scheduling.models import WorkingHours

URL = "/api/v1/availability/"
TASHKENT = zoneinfo.ZoneInfo("Asia/Tashkent")

FROZEN_NOW = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
def provider(provider, service):
    provider.services.add(service)
    return provider


def _future_date(days: int) -> date:
    return FROZEN_NOW.astimezone(TASHKENT).date() + timedelta(days=days)


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_public_access_no_auth(api_client: APIClient, provider, service):
    d = _future_date(2)
    WorkingHours.objects.create(
        provider=provider, weekday=d.weekday(), start_time=time(9, 0), end_time=time(17, 0)
    )

    response = api_client.get(URL, {"service": service.id, "date_from": d, "date_to": d})

    assert response.status_code == 200


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_response_shape_covers_every_date_including_empty(api_client: APIClient, provider, service):
    d1 = _future_date(2)
    d2 = _future_date(3)
    WorkingHours.objects.create(
        provider=provider, weekday=d1.weekday(), start_time=time(9, 0), end_time=time(10, 0)
    )
    # deliberately no WorkingHours for d2 -> its "slots" list must still appear, empty.

    response = api_client.get(URL, {"service": service.id, "date_from": d1, "date_to": d2})

    body = response.json()
    assert body["timezone"] == provider.business.timezone
    assert [entry["date"] for entry in body["dates"]] == [d1.isoformat(), d2.isoformat()]
    assert len(body["dates"][0]["slots"]) > 0
    assert body["dates"][1]["slots"] == []
    first_slot = body["dates"][0]["slots"][0]
    assert first_slot["start"].endswith("Z")
    assert first_slot["provider_ids"] == [provider.id]


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_missing_service_returns_404(api_client: APIClient):
    d = _future_date(2)
    response = api_client.get(URL, {"service": 999999, "date_from": d, "date_to": d})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "service_not_found"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_inactive_service_returns_404(api_client: APIClient, service):
    service.is_active = False
    service.save()
    d = _future_date(2)

    response = api_client.get(URL, {"service": service.id, "date_from": d, "date_to": d})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "service_not_found"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_provider_not_offering_service_returns_404(api_client: APIClient, service, other_provider):
    d = _future_date(2)

    response = api_client.get(
        URL, {"service": service.id, "provider": other_provider.id, "date_from": d, "date_to": d}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "provider_not_found"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_provider_from_another_business_returns_404(api_client: APIClient, service, other_business):
    from apps.accounts.models import User
    from apps.catalog.models import Provider

    other_business_user = User.objects.create_user(
        email="foreign@example.com",
        password="x",
        full_name="F",
        role=User.Role.PROVIDER,
        business=other_business,
    )
    other_business_provider = Provider.objects.create(
        user=other_business_user, business=other_business
    )
    d = _future_date(2)

    response = api_client.get(
        URL,
        {
            "service": service.id,
            "provider": other_business_provider.id,
            "date_from": d,
            "date_to": d,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "provider_not_found"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_date_to_before_date_from_returns_400(api_client: APIClient, service):
    d = _future_date(2)

    response = api_client.get(
        URL, {"service": service.id, "date_from": d, "date_to": d - timedelta(days=1)}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
@override_settings(AVAILABILITY_MAX_QUERY_DAYS=3)
def test_range_exceeding_max_query_days_returns_400(api_client: APIClient, service):
    d = _future_date(2)

    response = api_client.get(
        URL, {"service": service.id, "date_from": d, "date_to": d + timedelta(days=5)}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_date_from_in_the_past_returns_400(api_client: APIClient, service):
    yesterday = FROZEN_NOW.astimezone(TASHKENT).date() - timedelta(days=1)

    response = api_client.get(
        URL, {"service": service.id, "date_from": yesterday, "date_to": yesterday}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
@time_machine.travel(FROZEN_NOW)
def test_query_count_constant_across_day_range_and_provider_count(
    api_client: APIClient, provider, other_provider, service
):
    other_provider.services.add(service)
    for weekday in range(7):
        WorkingHours.objects.create(
            provider=provider, weekday=weekday, start_time=time(9, 0), end_time=time(17, 0)
        )
        WorkingHours.objects.create(
            provider=other_provider, weekday=weekday, start_time=time(9, 0), end_time=time(17, 0)
        )

    d = _future_date(2)
    max_days = 14

    with CaptureQueriesContext(connection) as one_day:
        api_client.get(URL, {"service": service.id, "date_from": d, "date_to": d})
    one_day_count = len(one_day.captured_queries)

    with CaptureQueriesContext(connection) as full_range:
        api_client.get(
            URL,
            {"service": service.id, "date_from": d, "date_to": d + timedelta(days=max_days - 1)},
        )
    full_range_count = len(full_range.captured_queries)

    assert one_day_count == full_range_count
    assert one_day_count <= 10
