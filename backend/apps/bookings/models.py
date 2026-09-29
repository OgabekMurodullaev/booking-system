from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.db.models import Q


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    provider = models.ForeignKey(
        "catalog.Provider", on_delete=models.CASCADE, related_name="bookings"
    )
    service = models.ForeignKey(
        "catalog.Service", on_delete=models.CASCADE, related_name="bookings"
    )
    time_range = DateTimeRangeField()
    blocked_range = DateTimeRangeField()
    status = models.CharField(max_length=20, choices=Status.choices)
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    duration_snapshot = models.PositiveIntegerField()
    expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_late_cancellation = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "status"], name="booking_provider_status_idx"),
            models.Index(fields=["customer", "created_at"], name="booking_customer_created_idx"),
        ]
        constraints = [
            ExclusionConstraint(
                name="booking_no_provider_overlap",
                expressions=[("provider", "="), ("blocked_range", "&&")],
                condition=Q(status__in=["pending", "confirmed"]),
            ),
            ExclusionConstraint(
                name="booking_no_customer_overlap",
                expressions=[("customer", "="), ("time_range", "&&")],
                condition=Q(status__in=["pending", "confirmed"]),
            ),
            models.UniqueConstraint(
                fields=["customer", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="booking_unique_idempotency_key",
            ),
            models.CheckConstraint(
                condition=(Q(status="pending") & Q(expires_at__isnull=False))
                | (~Q(status="pending") & Q(expires_at__isnull=True)),
                name="booking_pending_requires_expiry",
            ),
        ]

    def __str__(self) -> str:
        return f"Booking#{self.pk} {self.provider_id} {self.status}"


class BookingStatusLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="status_logs")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Booking#{self.booking_id}: {self.from_status} -> {self.to_status}"
