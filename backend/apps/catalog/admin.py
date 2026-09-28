from django.contrib import admin

from .models import Business, Provider, Service


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "timezone", "auto_confirm", "cancellation_window_hours"]
    search_fields = ["name"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "duration_minutes", "price", "buffer_minutes", "is_active"]
    list_filter = ["business", "is_active"]
    search_fields = ["name"]


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "is_active"]
    list_filter = ["business", "is_active"]
    search_fields = ["user__email", "user__full_name"]
    filter_horizontal = ["services"]
