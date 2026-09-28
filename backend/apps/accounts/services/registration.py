from django.db import IntegrityError

from apps.accounts.models import User
from apps.common.exceptions import DomainError


def register_customer(*, email: str, password: str, full_name: str, timezone: str) -> User:
    try:
        return User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            timezone=timezone,
            role=User.Role.CUSTOMER,
        )
    except IntegrityError as exc:
        # The serializer's uniqueness check is a plain SELECT and can race with a
        # concurrent registration for the same email; the DB constraint is the real
        # guarantee. Map that race to the same envelope as the normal duplicate-email
        # validation error instead of leaking a raw 500.
        raise DomainError(
            "A user with this email already exists.",
            code="validation_error",
            details={"email": ["A user with this email already exists."]},
            http_status=400,
        ) from exc
