from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from rest_framework import serializers

from apps.accounts.models import User
from apps.catalog.models import Provider, Service
from apps.catalog.services.providers import create_provider
from apps.common.exceptions import DomainError


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "business",
            "name",
            "description",
            "duration_minutes",
            "price",
            "buffer_minutes",
            "is_active",
        ]
        read_only_fields = ["id", "business", "is_active"]


class ServiceAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "business",
            "name",
            "description",
            "duration_minutes",
            "price",
            "buffer_minutes",
            "is_active",
        ]
        read_only_fields = ["id", "business", "is_active"]

    def validate_duration_minutes(self, value: int) -> int:
        if not (5 <= value <= 480):
            raise serializers.ValidationError("Must be between 5 and 480 minutes.")
        if value % 5 != 0:
            raise serializers.ValidationError("Must be a multiple of 5 minutes.")
        return value

    def validate_buffer_minutes(self, value: int) -> int:
        if not (0 <= value <= 120):
            raise serializers.ValidationError("Must be between 0 and 120 minutes.")
        return value


class ProviderUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name"]


class ProviderSerializer(serializers.ModelSerializer):
    user = ProviderUserSerializer(read_only=True)
    services = ServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Provider
        fields = ["id", "user", "business", "services", "is_active"]
        read_only_fields = ["id", "user", "business", "services", "is_active"]


class ProviderCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField()
    password = serializers.CharField(write_only=True)
    service_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )

    def validate_password(self, value: str) -> str:
        temp_user = User(
            email=self.initial_data.get("email", ""),
            full_name=self.initial_data.get("full_name", ""),
        )
        try:
            validate_password(value, user=temp_user)
        except django_exceptions.ValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data: dict) -> Provider:
        return create_provider(
            business=validated_data["business"],
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            password=validated_data["password"],
            service_ids=validated_data.get("service_ids", []),
        )


class ProviderUpdateSerializer(serializers.ModelSerializer):
    service_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = Provider
        fields = ["id", "is_active", "service_ids"]
        read_only_fields = ["id"]

    def update(self, instance: Provider, validated_data: dict) -> Provider:
        service_ids = validated_data.pop("service_ids", None)
        instance = super().update(instance, validated_data)
        if service_ids is not None:
            invalid = Service.objects.filter(id__in=service_ids).exclude(business=instance.business)
            if invalid.exists():
                raise DomainError(
                    "All services must belong to the provider's business.",
                    code="service_wrong_business",
                    details={"service_ids": list(invalid.values_list("id", flat=True))},
                    http_status=400,
                )
            instance.services.set(Service.objects.filter(id__in=service_ids))
        return instance
