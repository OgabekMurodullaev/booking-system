from django.db import IntegrityError, OperationalError, transaction

from apps.accounts.models import User
from apps.catalog.models import Business, Provider, Service
from apps.common.db import is_deadlock
from apps.common.exceptions import DomainError


def create_provider(
    *,
    business: Business,
    email: str,
    full_name: str,
    password: str,
    service_ids: list[int],
) -> Provider:
    invalid_services = Service.objects.filter(id__in=service_ids).exclude(business=business)
    if invalid_services.exists():
        raise DomainError(
            "All services must belong to the provider's business.",
            code="service_wrong_business",
            details={"service_ids": list(invalid_services.values_list("id", flat=True))},
            http_status=400,
        )

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=User.Role.PROVIDER,
                business=business,
            )
            provider = Provider.objects.create(user=user, business=business)
            if service_ids:
                provider.services.set(Service.objects.filter(id__in=service_ids))
    except (IntegrityError, OperationalError) as exc:
        # See apps.accounts.services.registration.register_customer: a concurrent insert
        # racing the same unique email can occasionally deadlock (SQLSTATE 40P01) instead
        # of raising a clean IntegrityError — only swallow an OperationalError once that's
        # confirmed, never any other operational failure.
        if isinstance(exc, OperationalError) and not is_deadlock(exc):
            raise
        raise DomainError(
            "A user with this email already exists.",
            code="validation_error",
            details={"email": ["A user with this email already exists."]},
            http_status=400,
        ) from exc

    return provider
