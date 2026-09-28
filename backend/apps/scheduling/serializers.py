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
