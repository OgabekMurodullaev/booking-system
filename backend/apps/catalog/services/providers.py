from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.catalog.models import Business, Provider, Service
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
    except IntegrityError as exc:
        raise DomainError(
            "A user with this email already exists.",
            code="validation_error",
            details={"email": ["A user with this email already exists."]},
            http_status=400,
        ) from exc

    return provider
