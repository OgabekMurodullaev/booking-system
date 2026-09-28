from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Booking, BookingStatusLog

_datetime_field = serializers.DateTimeField()


class BookingStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingStatusLog
        fields = ["id", "from_status", "to_status", "actor", "reason", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer",
            "provider",
            "service",
            "start",
            "end",
            "status",
            "price_snapshot",
            "duration_snapshot",
            "expires_at",
            "submitted_at",
            "is_late_cancellation",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DateTimeField)
    def get_start(self, obj: Booking):
        return _datetime_field.to_representation(obj.time_range.lower)

    @extend_schema_field(serializers.DateTimeField)
    def get_end(self, obj: Booking):
        return _datetime_field.to_representation(obj.time_range.upper)


class BookingDetailSerializer(BookingSerializer):
    status_logs = BookingStatusLogSerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = [*BookingSerializer.Meta.fields, "status_logs"]
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    provider = serializers.IntegerField(required=False, allow_null=True)
    start = serializers.DateTimeField()


class CancelBookingSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
