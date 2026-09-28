import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Business, Service

SERVICES_URL = "/api/v1/services/"


def _detail_url(pk: int) -> str:
    return f"/api/v1/services/{pk}/"


@pytest.mark.django_db
def test_public_list_shows_only_active(api_client: APIClient, business: Business):
    Service.objects.create(business=business, name="Active", duration_minutes=30, price="10.00")
    Service.objects.create(
        business=business,
        name="Inactive",
        duration_minutes=30,
        price="10.00",
        is_active=False,
    )

    response = api_client.get(SERVICES_URL)

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["results"]]
    assert names == ["Active"]


@pytest.mark.django_db
def test_admin_list_shows_own_business_active_and_inactive(
    admin_client: APIClient, business: Business, other_business: Business
):
    Service.objects.create(
        business=business, name="Mine Active", duration_minutes=30, price="10.00"
    )
    Service.objects.create(
        business=business, name="Mine Inactive", duration_minutes=30, price="10.00", is_active=False
    )
    Service.objects.create(
        business=other_business, name="Not Mine", duration_minutes=30, price="10.00"
    )

    response = admin_client.get(SERVICES_URL)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["results"]}
    assert names == {"Mine Active", "Mine Inactive"}


@pytest.mark.django_db
def test_create_forces_own_business_ignoring_body(
    admin_client: APIClient, business: Business, other_business: Business
):
    response = admin_client.post(
        SERVICES_URL,
        {
            "business": other_business.id,
            "name": "New Service",
            "duration_minutes": 30,
            "price": "25.00",
        },
        format="json",
    )

    assert response.status_code == 201
    service = Service.objects.get(name="New Service")
    assert service.business_id == business.id


@pytest.mark.django_db
def test_create_requires_admin(api_client: APIClient, provider_client: APIClient):
    payload = {"name": "X", "duration_minutes": 30, "price": "10.00"}

    assert api_client.post(SERVICES_URL, payload, format="json").status_code in (401, 403)
    assert provider_client.post(SERVICES_URL, payload, format="json").status_code == 403


@pytest.mark.django_db
def test_create_invalid_duration_rejected(admin_client: APIClient):
    response = admin_client.post(
        SERVICES_URL,
        {"name": "Bad", "duration_minutes": 7, "price": "10.00"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_soft_delete_deactivates_but_keeps_row(admin_client: APIClient, service: Service):
    response = admin_client.delete(_detail_url(service.id))

    assert response.status_code == 204
    service.refresh_from_db()
    assert service.is_active is False


@pytest.mark.django_db
def test_public_detail_hides_inactive_service(api_client: APIClient, service: Service):
    service.is_active = False
    service.save(update_fields=["is_active"])

    response = api_client.get(_detail_url(service.id))

    assert response.status_code == 404


@pytest.mark.django_db
def test_owning_admin_can_see_inactive_service_detail(admin_client: APIClient, service: Service):
    service.is_active = False
    service.save(update_fields=["is_active"])

    response = admin_client.get(_detail_url(service.id))

    assert response.status_code == 200
