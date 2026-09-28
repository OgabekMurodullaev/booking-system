from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.permissions import IsBusinessAdminOrOwnProvider

from .models import TimeOff, WorkingHours
from .serializers import TimeOffSerializer, WorkingHoursSerializer
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
