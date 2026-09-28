import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Business, Provider, Service


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def business() -> Business:
    return Business.objects.create(name="Test Salon", timezone="Asia/Tashkent")


@pytest.fixture
def other_business() -> Business:
    return Business.objects.create(name="Other Salon", timezone="Asia/Tashkent")


@pytest.fixture
def admin_user(business: Business) -> User:
    return User.objects.create_user(
        email="admin@example.com",
        password="a-very-strong-pass-123",
        full_name="Business Admin",
        role=User.Role.ADMIN,
        business=business,
    )


@pytest.fixture
def other_admin_user(other_business: Business) -> User:
    return User.objects.create_user(
        email="other-admin@example.com",
        password="a-very-strong-pass-123",
        full_name="Other Admin",
        role=User.Role.ADMIN,
        business=other_business,
    )


@pytest.fixture
def service(business: Business) -> Service:
    return Service.objects.create(
        business=business,
        name="Haircut",
        duration_minutes=30,
        price="20.00",
        buffer_minutes=10,
    )


@pytest.fixture
def customer() -> User:
    return User.objects.create_user(
        email="customer@example.com", password="a-very-strong-pass-123", full_name="Customer"
    )


@pytest.fixture
def other_customer() -> User:
    return User.objects.create_user(
        email="other-customer@example.com",
        password="a-very-strong-pass-123",
        full_name="Other Customer",
    )


@pytest.fixture
def provider(business: Business) -> Provider:
    user = User.objects.create_user(
        email="provider@example.com",
        password="a-very-strong-pass-123",
        full_name="Test Provider",
        role=User.Role.PROVIDER,
        business=business,
    )
    return Provider.objects.create(user=user, business=business)


@pytest.fixture
def other_provider(business: Business) -> Provider:
    user = User.objects.create_user(
        email="other-provider@example.com",
        password="a-very-strong-pass-123",
        full_name="Other Provider",
        role=User.Role.PROVIDER,
        business=business,
    )
    return Provider.objects.create(user=user, business=business)


@pytest.fixture
def admin_client(admin_user: User) -> APIClient:
    return auth_client(admin_user)


@pytest.fixture
def other_admin_client(other_admin_user: User) -> APIClient:
    return auth_client(other_admin_user)


@pytest.fixture
def provider_client(provider: Provider) -> APIClient:
    return auth_client(provider.user)
