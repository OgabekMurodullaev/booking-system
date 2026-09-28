from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.expressions import RawSQL


class Business(models.Model):
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=64, default="UTC")
    auto_confirm = models.BooleanField(default=False)
    cancellation_window_hours = models.PositiveIntegerField(default=24)

    def __str__(self) -> str:
        return self.name


class Service(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    buffer_minutes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=5) & Q(duration_minutes__lte=480),
                name="service_duration_range",
            ),
            models.CheckConstraint(
                condition=RawSQL(
                    "duration_minutes %% 5 = 0", (), output_field=models.BooleanField()
                ),
                name="service_duration_step_of_5",
            ),
            models.CheckConstraint(
                condition=Q(buffer_minutes__gte=0) & Q(buffer_minutes__lte=120),
                name="service_buffer_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.business_id})"


class Provider(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_profile"
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="providers")
    services = models.ManyToManyField(Service, related_name="providers", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.user.full_name
