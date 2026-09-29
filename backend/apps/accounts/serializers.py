import zoneinfo

from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User
from apps.accounts.services.registration import register_customer


class UserSerializer(serializers.ModelSerializer):
    provider_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "timezone", "provider_id"]
        read_only_fields = ["id", "email", "role", "provider_id"]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_provider_id(self, obj: User) -> int | None:
        # The frontend has no other way to learn "my own Provider row id" — the
        # public/customer-facing providers list is cross-business and paginated, so
        # a provider-role user can't reliably find themselves in it. Exposed here
        # instead of adding a dedicated endpoint for one integer.
        provider = getattr(obj, "provider_profile", None)
        return provider.id if provider else None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "password", "timezone", "role"]
        read_only_fields = ["id", "role"]

    def validate_password(self, value: str) -> str:
        # Build an unsaved User so UserAttributeSimilarityValidator can reject
        # passwords that are too similar to the submitted email/full_name —
        # without a user instance it silently skips that check entirely.
        temp_user = User(
            email=self.initial_data.get("email", ""),
            full_name=self.initial_data.get("full_name", ""),
        )
        try:
            validate_password(value, user=temp_user)
        except django_exceptions.ValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate_timezone(self, value: str) -> str:
        if value not in zoneinfo.available_timezones():
            raise serializers.ValidationError("Not a valid IANA timezone.")
        return value

    def validate_email(self, value: str) -> str:
        value = User.objects.normalize_email(value).lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data: dict) -> User:
        return register_customer(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            timezone=validated_data.get("timezone", "UTC"),
        )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LoginResponseSerializer(serializers.Serializer):
    # TokenObtainPairSerializer.validate() injects access/refresh/user onto the
    # response dict outside its own declared `fields`, so drf-spectacular's static
    # introspection can't see them from EmailTokenObtainPairSerializer alone — this
    # documents the actual runtime shape for schema/codegen accuracy (CLAUDE.md §7).
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
