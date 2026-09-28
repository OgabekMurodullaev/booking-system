from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Provider, Service
from apps.common.exceptions import DomainError

from .filters import BookingFilterSet
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingSerializer,
    CancelBookingSerializer,
)
from .services.booking import (
    cancel_booking,
    complete_booking,
    confirm_booking,
    create_hold,
    submit_booking,
)


def _resolve_service(service_id) -> Service:
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


def _resolve_provider(provider_id, service: Service) -> Provider | None:
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


def _scoped_queryset(user):
    if user.role == user.Role.CUSTOMER:
        return Booking.objects.filter(customer=user)
    if user.role == user.Role.PROVIDER:
        provider = getattr(user, "provider_profile", None)
        if provider is None:
            return Booking.objects.none()
        return Booking.objects.filter(provider=provider)
    if user.role == user.Role.ADMIN:
        return Booking.objects.filter(provider__business=user.business)
    return Booking.objects.none()


class BookingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = BookingFilterSet

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookingCreateSerializer
        return BookingSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        return (
            _scoped_queryset(self.request.user)
            .select_related("customer", "provider__user", "service")
            .order_by("time_range")
        )

    @extend_schema(responses=BookingDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = _resolve_service(data["service"])
        provider = _resolve_provider(data.get("provider"), service)
        idempotency_key = request.headers.get("Idempotency-Key")

        result = create_hold(
            customer=request.user,
            service=service,
            start=data["start"],
            provider=provider,
            idempotency_key=idempotency_key,
        )
        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return Response(BookingDetailSerializer(result.booking).data, status=response_status)


class BookingDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        return (
            _scoped_queryset(self.request.user)
            .select_related("customer", "provider__user", "service")
            .prefetch_related("status_logs")
        )


class BookingSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=BookingDetailSerializer)
    def post(self, request, pk):
        booking = get_object_or_404(_scoped_queryset(request.user), pk=pk)
        booking = submit_booking(booking, actor=request.user)
        return Response(BookingDetailSerializer(booking).data)


class BookingConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=BookingDetailSerializer)
    def post(self, request, pk):
        booking = get_object_or_404(_scoped_queryset(request.user), pk=pk)
        booking = confirm_booking(booking, actor=request.user)
        return Response(BookingDetailSerializer(booking).data)


class BookingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=CancelBookingSerializer, responses=BookingDetailSerializer)
    def post(self, request, pk):
        booking = get_object_or_404(_scoped_queryset(request.user), pk=pk)
        serializer = CancelBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = cancel_booking(
            booking, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        return Response(BookingDetailSerializer(booking).data)


class BookingCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=BookingDetailSerializer)
    def post(self, request, pk):
        booking = get_object_or_404(_scoped_queryset(request.user), pk=pk)
        booking = complete_booking(booking, actor=request.user)
        return Response(BookingDetailSerializer(booking).data)
