import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_normalizes_email_to_lowercase():
    user = User.objects.create_user(
        email="Foo@Example.COM", password="s3cure-pass!23", full_name="Foo Bar"
    )

    assert user.email == "foo@example.com"


@pytest.mark.django_db
def test_create_user_defaults_role_to_customer():
    user = User.objects.create_user(
        email="customer@example.com", password="s3cure-pass!23", full_name="Customer"
    )

    assert user.role == User.Role.CUSTOMER
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_superuser_sets_admin_role_and_staff_flags():
    user = User.objects.create_superuser(
        email="admin@example.com", password="s3cure-pass!23", full_name="Admin"
    )

    assert user.role == User.Role.ADMIN
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_invalid_timezone_rejected_at_model_level():
    user = User(email="tz@example.com", full_name="TZ", timezone="Not/AZone")

    with pytest.raises(ValidationError):
        user.full_clean(exclude=["password"])
