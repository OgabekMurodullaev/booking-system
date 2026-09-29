from django.db import IntegrityError, OperationalError

from apps.accounts.models import User
from apps.common.db import is_deadlock
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
    except (IntegrityError, OperationalError) as exc:
        # The serializer's uniqueness check is a plain SELECT and can race with a
        # concurrent registration for the same email; the DB constraint is the real
        # guarantee. Two concurrent inserts racing the same unique index can also
        # occasionally deadlock (Postgres SQLSTATE 40P01) instead of raising a clean
        # IntegrityError — a genuine Postgres behavior, not a schema bug — so an
        # OperationalError is only ever swallowed here when it's confirmed to be that.
        # Either way, map the race to the same envelope as the normal duplicate-email
        # validation error instead of leaking a raw 500.
        if isinstance(exc, OperationalError) and not is_deadlock(exc):
            raise
        raise DomainError(
            "A user with this email already exists.",
            code="validation_error",
            details={"email": ["A user with this email already exists."]},
            http_status=400,
        ) from exc
