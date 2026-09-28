from django.contrib import admin

from .models import TimeOff, WorkingHours


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ["provider", "weekday", "start_time", "end_time"]
    list_filter = ["weekday"]


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ["provider", "start", "end", "reason"]
