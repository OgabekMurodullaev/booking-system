import zoneinfo

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PROVIDER = "provider", "Provider"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    timezone = models.CharField(max_length=64, default="UTC")
    business = models.ForeignKey(
        "catalog.Business",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_lower_unique"),
            # Superusers (site-wide Django admin access) are exempt: they're an
            # implementation-level concept distinct from a business-scoped "admin"
            # role, and createsuperuser has no way to attach a Business up front.
            models.CheckConstraint(
                condition=~models.Q(role__in=["provider", "admin"])
                | models.Q(business__isnull=False)
                | models.Q(is_superuser=True),
                name="accounts_user_business_required_for_staff",
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        if self.timezone not in zoneinfo.available_timezones():
            raise ValidationError({"timezone": "Not a valid IANA timezone."})
