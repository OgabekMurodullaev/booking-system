import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Business, Provider, Service


@pytest.mark.django_db
def test_admin_cannot_see_another_business_service_in_list(
    admin_client: APIClient, other_business: Business
):
    Service.objects.create(
        business=other_business, name="Theirs", duration_minutes=30, price="10.00"
    )

    response = admin_client.get("/api/v1/services/")

    assert response.json()["results"] == []


@pytest.mark.django_db
def test_active_service_of_another_business_is_still_publicly_viewable(
    admin_client: APIClient, other_business: Business
):
    # Active services are public data (visible in the unscoped public list too) -
    # an admin seeing another business's *active* listing is not a privilege leak,
    # it's the same public view any anonymous visitor gets. Isolation is about the
    # admin's own management surface (list/inactive detail/write), not public data.
    theirs = Service.objects.create(
        business=other_business, name="Theirs", duration_minutes=30, price="10.00"
    )

    response = admin_client.get(f"/api/v1/services/{theirs.id}/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_gets_404_on_another_business_inactive_service_detail(
    admin_client: APIClient, other_business: Business
):
    theirs = Service.objects.create(
        business=other_business,
        name="Theirs",
        duration_minutes=30,
        price="10.00",
        is_active=False,
    )

    response = admin_client.get(f"/api/v1/services/{theirs.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_cannot_patch_another_business_service(
    admin_client: APIClient, other_business: Business
):
    theirs = Service.objects.create(
        business=other_business, name="Theirs", duration_minutes=30, price="10.00"
    )

    response = admin_client.patch(
        f"/api/v1/services/{theirs.id}/", {"name": "Hijacked"}, format="json"
    )

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.name == "Theirs"


@pytest.mark.django_db
def test_admin_cannot_delete_another_business_service(
    admin_client: APIClient, other_business: Business
):
    theirs = Service.objects.create(
        business=other_business, name="Theirs", duration_minutes=30, price="10.00"
    )

    response = admin_client.delete(f"/api/v1/services/{theirs.id}/")

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.is_active is True


@pytest.mark.django_db
def test_admin_gets_404_on_another_business_inactive_provider_detail(
    admin_client: APIClient, other_business: Business
):
    from apps.accounts.models import User

    other_user = User.objects.create_user(
        email="theirprovider@example.com",
        password="x",
        full_name="Theirs",
        role=User.Role.PROVIDER,
        business=other_business,
    )
    theirs = Provider.objects.create(user=other_user, business=other_business, is_active=False)

    response = admin_client.get(f"/api/v1/providers/{theirs.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_cannot_manage_another_business_provider_working_hours(
    admin_client: APIClient, other_business: Business
):
    from apps.accounts.models import User

    other_user = User.objects.create_user(
        email="theirprovider2@example.com",
        password="x",
        full_name="Theirs",
        role=User.Role.PROVIDER,
        business=other_business,
    )
    theirs = Provider.objects.create(user=other_user, business=other_business)

    response = admin_client.put(
        f"/api/v1/providers/{theirs.id}/working-hours/",
        [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"}],
        format="json",
    )

    assert response.status_code == 403
