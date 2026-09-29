from datetime import timedelta

from django.utils import timezone
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
    has_time_off_conflict = serializers.BooleanField(read_only=True, default=False)
    would_be_late_cancellation = serializers.SerializerMethodField()

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
            "has_time_off_conflict",
            "would_be_late_cancellation",
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

    @extend_schema_field(serializers.BooleanField)
    def get_would_be_late_cancellation(self, obj: Booking) -> bool:
        # Lets the frontend warn *before* the customer confirms a cancellation,
        # rather than only reporting is_late_cancellation after the fact — the
        # cancellation window is a business setting the client has no other way
        # to see (no /businesses/ endpoint exists), so this mirrors the same
        # window/now() check transition_booking() itself uses at cancel time.
        if obj.status != Booking.Status.CONFIRMED:
            return False
        window = timedelta(hours=obj.provider.business.cancellation_window_hours)
        return timezone.now() >= obj.time_range.lower - window


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
