from datetime import time

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Business, Provider
from apps.common.exceptions import DomainError
from apps.scheduling.models import WorkingHours
from apps.scheduling.services.working_hours import validate_no_overlap


@pytest.mark.django_db
def test_start_before_end_check_constraint(provider: Provider):
    with pytest.raises(IntegrityError), transaction.atomic():
        WorkingHours.objects.create(
            provider=provider, weekday=0, start_time=time(12, 0), end_time=time(9, 0)
        )


@pytest.mark.django_db
def test_weekday_range_check_constraint(provider: Provider):
    with pytest.raises(IntegrityError), transaction.atomic():
        WorkingHours.objects.create(
            provider=provider, weekday=7, start_time=time(9, 0), end_time=time(12, 0)
        )


def test_validate_no_overlap_rejects_overlapping_intervals():
    # Enforced here (service-level), not as a DB exclusion constraint: Postgres has no
    # built-in range type for bare `time`, and unlike double-booking this invariant is
    # only ever broken by a single admin/provider action, never a concurrent race.
    with pytest.raises(DomainError):
        validate_no_overlap([(time(9, 0), time(13, 0)), (time(12, 0), time(17, 0))])


def test_validate_no_overlap_allows_lunch_break_gap():
    validate_no_overlap([(time(9, 0), time(13, 0)), (time(14, 0), time(18, 0))])


def test_validate_no_overlap_allows_back_to_back_intervals():
    validate_no_overlap([(time(9, 0), time(13, 0)), (time(13, 0), time(18, 0))])


@pytest.mark.django_db
def test_replace_all_admin_of_same_business_allowed(admin_client: APIClient, provider: Provider):
    response = admin_client.put(
        f"/api/v1/providers/{provider.id}/working-hours/",
        [
            {"weekday": 0, "start_time": "09:00", "end_time": "13:00"},
            {"weekday": 0, "start_time": "14:00", "end_time": "18:00"},
        ],
        format="json",
    )

    assert response.status_code == 200
    assert WorkingHours.objects.filter(provider=provider).count() == 2


@pytest.mark.django_db
def test_replace_all_provider_themselves_allowed(provider_client: APIClient, provider: Provider):
    response = provider_client.put(
        f"/api/v1/providers/{provider.id}/working-hours/",
        [{"weekday": 1, "start_time": "09:00", "end_time": "17:00"}],
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_replace_all_different_provider_forbidden(business: Business, provider: Provider):
    from apps.conftest import auth_client

    other_provider_user = User.objects.create_user(
        email="other-provider@example.com",
        password="x",
        full_name="Other",
        role=User.Role.PROVIDER,
        business=business,
    )
    other_provider = Provider.objects.create(user=other_provider_user, business=business)
    client = auth_client(other_provider_user)

    response = client.put(
        f"/api/v1/providers/{provider.id}/working-hours/",
        [{"weekday": 0, "start_time": "09:00", "end_time": "17:00"}],
        format="json",
    )

    assert response.status_code == 403
    assert other_provider.id != provider.id


@pytest.mark.django_db
def test_replace_all_admin_of_different_business_forbidden(
    other_admin_client: APIClient, provider: Provider
):
    response = other_admin_client.put(
        f"/api/v1/providers/{provider.id}/working-hours/",
        [{"weekday": 0, "start_time": "09:00", "end_time": "17:00"}],
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_overlapping_intervals_rejected_via_api(admin_client: APIClient, provider: Provider):
    response = admin_client.put(
        f"/api/v1/providers/{provider.id}/working-hours/",
        [
            {"weekday": 0, "start_time": "09:00", "end_time": "13:00"},
            {"weekday": 0, "start_time": "12:00", "end_time": "17:00"},
        ],
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "overlapping_working_hours"


@pytest.mark.django_db
def test_get_working_hours_is_public(api_client: APIClient, provider: Provider):
    WorkingHours.objects.create(
        provider=provider, weekday=0, start_time=time(9, 0), end_time=time(17, 0)
    )

    response = api_client.get(f"/api/v1/providers/{provider.id}/working-hours/")

    assert response.status_code == 200
    assert len(response.json()) == 1
