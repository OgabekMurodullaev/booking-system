from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Provider
from apps.scheduling.models import TimeOff

LIST_URL = "/api/v1/providers/{}/time-off/"
DETAIL_URL = "/api/v1/providers/{}/time-off/{}/"


@pytest.mark.django_db
def test_start_before_end_check_constraint(provider: Provider):
    now = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeOff.objects.create(provider=provider, start=now, end=now - timedelta(hours=1))


@pytest.mark.django_db
def test_admin_can_create_time_off(admin_client: APIClient, provider: Provider):
    now = timezone.now()
    response = admin_client.post(
        LIST_URL.format(provider.id),
        {"start": now.isoformat(), "end": (now + timedelta(days=1)).isoformat(), "reason": "Leave"},
        format="json",
    )

    assert response.status_code == 201
    assert TimeOff.objects.filter(provider=provider).count() == 1


@pytest.mark.django_db
def test_provider_can_create_own_time_off(provider_client: APIClient, provider: Provider):
    now = timezone.now()
    response = provider_client.post(
        LIST_URL.format(provider.id),
        {"start": now.isoformat(), "end": (now + timedelta(hours=2)).isoformat()},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_unrelated_user_cannot_list_time_off(api_client: APIClient, provider: Provider):
    response = api_client.get(LIST_URL.format(provider.id))

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_admin_of_different_business_cannot_create_time_off(
    other_admin_client: APIClient, provider: Provider
):
    now = timezone.now()
    response = other_admin_client.post(
        LIST_URL.format(provider.id),
        {"start": now.isoformat(), "end": (now + timedelta(hours=1)).isoformat()},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_can_delete_time_off(admin_client: APIClient, provider: Provider):
    now = timezone.now()
    time_off = TimeOff.objects.create(provider=provider, start=now, end=now + timedelta(hours=1))

    response = admin_client.delete(DETAIL_URL.format(provider.id, time_off.id))

    assert response.status_code == 204
    assert not TimeOff.objects.filter(id=time_off.id).exists()
