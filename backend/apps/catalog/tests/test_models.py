import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.catalog.models import Business, Provider, Service


@pytest.mark.django_db
def test_service_duration_must_be_multiple_of_5(business: Business):
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(business=business, name="Bad", duration_minutes=7, price="10.00")


@pytest.mark.django_db
@pytest.mark.parametrize("duration", [0, 4, 481, 500])
def test_service_duration_must_be_in_range(business: Business, duration: int):
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(
            business=business, name="Bad", duration_minutes=duration, price="10.00"
        )


@pytest.mark.django_db
def test_service_buffer_must_be_in_range(business: Business):
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(
            business=business,
            name="Bad",
            duration_minutes=30,
            price="10.00",
            buffer_minutes=121,
        )


@pytest.mark.django_db
def test_service_valid_values_saved(business: Business):
    service = Service.objects.create(
        business=business, name="Good", duration_minutes=45, price="15.50", buffer_minutes=15
    )
    assert service.pk is not None


@pytest.mark.django_db
def test_provider_user_must_be_unique(business: Business):
    user = User.objects.create_user(
        email="dup-provider@example.com",
        password="x",
        full_name="P",
        role=User.Role.PROVIDER,
        business=business,
    )
    Provider.objects.create(user=user, business=business)

    with pytest.raises(IntegrityError), transaction.atomic():
        Provider.objects.create(user=user, business=business)
