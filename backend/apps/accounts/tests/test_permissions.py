import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.catalog.models import Business
from apps.common.permissions import IsBusinessAdmin, IsCustomer, IsProvider

factory = APIRequestFactory()


def _fake_request(user):
    request = Request(factory.get("/fake/"))
    request.user = user
    return request


@pytest.mark.django_db
def test_is_customer_permission(business: Business):
    customer = User.objects.create_user(email="c@example.com", password="x", full_name="C")
    provider = User.objects.create_user(
        email="p@example.com",
        password="x",
        full_name="P",
        role=User.Role.PROVIDER,
        business=business,
    )

    assert IsCustomer().has_permission(_fake_request(customer), None) is True
    assert IsCustomer().has_permission(_fake_request(provider), None) is False


@pytest.mark.django_db
def test_is_provider_permission(business: Business):
    provider = User.objects.create_user(
        email="p2@example.com",
        password="x",
        full_name="P",
        role=User.Role.PROVIDER,
        business=business,
    )
    customer = User.objects.create_user(email="c2@example.com", password="x", full_name="C")

    assert IsProvider().has_permission(_fake_request(provider), None) is True
    assert IsProvider().has_permission(_fake_request(customer), None) is False


@pytest.mark.django_db
def test_is_business_admin_permission():
    admin = User.objects.create_superuser(email="a@example.com", password="x", full_name="A")
    customer = User.objects.create_user(email="c3@example.com", password="x", full_name="C")

    assert IsBusinessAdmin().has_permission(_fake_request(admin), None) is True
    assert IsBusinessAdmin().has_permission(_fake_request(customer), None) is False
