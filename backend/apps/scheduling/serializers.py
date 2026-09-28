from django.conf import settings
from rest_framework import serializers

from .models import TimeOff, WorkingHours


class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["id", "weekday", "start_time", "end_time"]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError({"end_time": "Must be after start_time."})
        return attrs

    def validate_weekday(self, value: int) -> int:
        if not (0 <= value <= 6):
            raise serializers.ValidationError("Must be between 0 (Monday) and 6 (Sunday).")
        return value


class TimeOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeOff
        fields = ["id", "start", "end", "reason"]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start", getattr(self.instance, "start", None))
        end = attrs.get("end", getattr(self.instance, "end", None))
        if start is not None and end is not None and start >= end:
            raise serializers.ValidationError({"end": "Must be after start."})
        return attrs


class AvailabilityQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()

    def validate(self, attrs: dict) -> dict:
        date_from = attrs["date_from"]
        date_to = attrs["date_to"]

        if date_to < date_from:
            raise serializers.ValidationError({"date_to": "Must not be before date_from."})

        max_days = settings.AVAILABILITY_MAX_QUERY_DAYS
        if (date_to - date_from).days + 1 > max_days:
            raise serializers.ValidationError(
                {"date_to": f"Range must not exceed {max_days} days."}
            )

        today = self.context["today"]
        if date_from < today:
            raise serializers.ValidationError({"date_from": "Must not be in the past."})

        return attrs


class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    provider_ids = serializers.ListField(child=serializers.IntegerField())


class AvailabilityDateSerializer(serializers.Serializer):
    date = serializers.DateField()
    slots = SlotSerializer(many=True)


class AvailabilityResponseSerializer(serializers.Serializer):
    timezone = serializers.CharField()
    dates = AvailabilityDateSerializer(many=True)
