import pytest
from django.db.models import ProtectedError

from apps.accounts.models import User
from apps.catalog.models import Business, Provider


@pytest.mark.django_db
def test_business_with_staff_cannot_be_deleted(business: Business, admin_user: User):
    with pytest.raises(ProtectedError):
        business.delete()
    assert Business.objects.filter(pk=business.pk).exists()


@pytest.mark.django_db
def test_business_can_be_deleted_after_staff_removed(business: Business, provider: Provider):
    provider_user = provider.user
    provider_user.delete()

    business.delete()

    assert not Business.objects.filter(pk=business.pk).exists()
    assert not Provider.objects.filter(pk=provider.pk).exists()
