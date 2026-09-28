from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone as django_timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Provider, Service
from apps.catalog.permissions import IsBusinessAdminOrOwnProvider
from apps.common.exceptions import DomainError

from .models import TimeOff, WorkingHours
from .serializers import (
    AvailabilityQuerySerializer,
    AvailabilityResponseSerializer,
    TimeOffSerializer,
    WorkingHoursSerializer,
)
from .services.availability import get_available_slots
from .services.working_hours import replace_working_hours


class WorkingHoursView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsBusinessAdminOrOwnProvider()]

    @extend_schema(responses=WorkingHoursSerializer(many=True))
    def get(self, request, provider_id):
        hours = WorkingHours.objects.filter(provider_id=provider_id)
        return Response(WorkingHoursSerializer(hours, many=True).data)

    @extend_schema(
        request=WorkingHoursSerializer(many=True), responses=WorkingHoursSerializer(many=True)
    )
    def put(self, request, provider_id):
        serializer = WorkingHoursSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        hours = replace_working_hours(self.provider, serializer.validated_data)
        return Response(WorkingHoursSerializer(hours, many=True).data)


class TimeOffListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsBusinessAdminOrOwnProvider]
    serializer_class = TimeOffSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TimeOff.objects.none()
        return TimeOff.objects.filter(provider_id=self.kwargs["provider_id"])

    def perform_create(self, serializer):
        serializer.save(provider=self.provider)


class TimeOffDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsBusinessAdminOrOwnProvider]
    serializer_class = TimeOffSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TimeOff.objects.none()
        return TimeOff.objects.filter(provider_id=self.kwargs["provider_id"])


class AvailabilityView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("service", int, required=True, description="Service id"),
            OpenApiParameter(
                "date_from", str, required=True, description="YYYY-MM-DD, business timezone"
            ),
            OpenApiParameter(
                "date_to", str, required=True, description="YYYY-MM-DD, business timezone"
            ),
            OpenApiParameter(
                "provider", int, required=False, description="Restrict to one provider"
            ),
        ],
        responses=AvailabilityResponseSerializer,
    )
    def get(self, request):
        service = self._resolve_service(request.query_params.get("service"))
        provider = self._resolve_provider(request.query_params.get("provider"), service)

        now = django_timezone.now()
        zone = ZoneInfo(service.business.timezone)
        today = now.astimezone(zone).date()

        query = AvailabilityQuerySerializer(data=request.query_params, context={"today": today})
        query.is_valid(raise_exception=True)
        date_from = query.validated_data["date_from"]
        date_to = query.validated_data["date_to"]

        slots = get_available_slots(
            service=service, date_from=date_from, date_to=date_to, provider=provider, now=now
        )

        slots_by_date = defaultdict(list)
        for slot in slots:
            slots_by_date[slot.start.astimezone(zone).date()].append(slot)

        day_count = (date_to - date_from).days + 1
        dates = [
            {
                "date": date_from + timedelta(days=offset),
                "slots": slots_by_date.get(date_from + timedelta(days=offset), []),
            }
            for offset in range(day_count)
        ]

        response = AvailabilityResponseSerializer(
            {"timezone": service.business.timezone, "dates": dates}
        )
        return Response(response.data)

    @staticmethod
    def _resolve_service(service_id: str | None) -> Service:
        if not service_id:
            raise DomainError(
                "service is required.",
                code="validation_error",
                details={"service": ["This field is required."]},
                http_status=400,
            )
        try:
            return Service.objects.select_related("business").get(pk=service_id, is_active=True)
        except (Service.DoesNotExist, ValueError) as exc:
            raise DomainError(
                "Service not found or inactive.", code="service_not_found", http_status=404
            ) from exc

    @staticmethod
    def _resolve_provider(provider_id: str | None, service: Service) -> Provider | None:
        if not provider_id:
            return None
        try:
            return Provider.objects.get(
                pk=provider_id, business=service.business, is_active=True, services=service
            )
        except (Provider.DoesNotExist, ValueError) as exc:
            raise DomainError(
                "Provider not found, inactive, or does not offer this service.",
                code="provider_not_found",
                http_status=404,
            ) from exc
