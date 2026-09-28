from django.db import models
from django.db.models import F, Q


class WorkingHours(models.Model):
    provider = models.ForeignKey(
        "catalog.Provider", on_delete=models.CASCADE, related_name="working_hours"
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")),
                name="workinghours_start_before_end",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="workinghours_weekday_range",
            ),
        ]
        ordering = ["weekday", "start_time"]

    def __str__(self) -> str:
        return f"{self.provider_id} weekday={self.weekday} {self.start_time}-{self.end_time}"


class TimeOff(models.Model):
    provider = models.ForeignKey(
        "catalog.Provider", on_delete=models.CASCADE, related_name="time_off"
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(start__lt=F("end")), name="timeoff_start_before_end"
            ),
        ]
        ordering = ["start"]

    def __str__(self) -> str:
        return f"{self.provider_id} {self.start}-{self.end}"
