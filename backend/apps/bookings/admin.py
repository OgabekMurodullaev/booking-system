from django.contrib import admin

from .models import Booking, BookingStatusLog


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "actor", "reason", "created_at"]

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "provider", "service", "status", "time_range"]
    list_filter = ["status", "provider__business"]
    search_fields = ["customer__email", "provider__user__email"]
    readonly_fields = [
        "customer",
        "provider",
        "service",
        "time_range",
        "blocked_range",
        "price_snapshot",
        "duration_snapshot",
        "expires_at",
        "submitted_at",
        "is_late_cancellation",
        "idempotency_key",
        "created_at",
        "updated_at",
    ]
    inlines = [BookingStatusLogInline]
