import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Business, Provider, Service

PROVIDERS_URL = "/api/v1/providers/"


def _detail_url(pk: int) -> str:
    return f"/api/v1/providers/{pk}/"


@pytest.mark.django_db
def test_admin_creates_provider_with_user_account(admin_client: APIClient, business: Business):
    response = admin_client.post(
        PROVIDERS_URL,
        {
            "email": "newprovider@example.com",
            "full_name": "New Provider",
            "password": "a-very-strong-pass-123",
        },
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(email="newprovider@example.com")
    assert user.role == User.Role.PROVIDER
    assert user.business_id == business.id
    provider = Provider.objects.get(user=user)
    assert provider.business_id == business.id


@pytest.mark.django_db
def test_provider_creation_assigns_services(
    admin_client: APIClient, business: Business, service: Service
):
    response = admin_client.post(
        PROVIDERS_URL,
        {
            "email": "withservices@example.com",
            "full_name": "Has Services",
            "password": "a-very-strong-pass-123",
            "service_ids": [service.id],
        },
        format="json",
    )

    assert response.status_code == 201
    provider = Provider.objects.get(user__email="withservices@example.com")
    assert list(provider.services.values_list("id", flat=True)) == [service.id]


@pytest.mark.django_db
def test_provider_creation_rejects_service_from_another_business(
    admin_client: APIClient, other_business: Business
):
    other_service = Service.objects.create(
        business=other_business, name="Foreign", duration_minutes=30, price="10.00"
    )

    response = admin_client.post(
        PROVIDERS_URL,
        {
            "email": "badassign@example.com",
            "full_name": "Bad Assign",
            "password": "a-very-strong-pass-123",
            "service_ids": [other_service.id],
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "service_wrong_business"
    assert not User.objects.filter(email="badassign@example.com").exists()


@pytest.mark.django_db
def test_public_list_shows_only_active_providers(api_client: APIClient, provider: Provider):
    provider.is_active = False
    provider.save(update_fields=["is_active"])

    response = api_client.get(PROVIDERS_URL)

    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.django_db
def test_admin_can_deactivate_provider(admin_client: APIClient, provider: Provider):
    response = admin_client.patch(_detail_url(provider.id), {"is_active": False}, format="json")

    assert response.status_code == 200
    provider.refresh_from_db()
    assert provider.is_active is False
