from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsBusinessAdmin

from .models import Provider, Service
from .serializers import (
    ProviderCreateSerializer,
    ProviderSerializer,
    ProviderUpdateSerializer,
    ServiceAdminSerializer,
    ServiceSerializer,
)


def _is_owner_admin(user, business_id) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.role == user.Role.ADMIN
        and user.business_id == business_id
    )


class ServiceListCreateView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsBusinessAdmin()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ServiceAdminSerializer
        return ServiceSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role == user.Role.ADMIN:
            return Service.objects.filter(business=user.business)
        return Service.objects.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)


class ServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsBusinessAdmin()]

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return ServiceSerializer
        return ServiceAdminSerializer

    def get_object(self):
        obj = get_object_or_404(Service, pk=self.kwargs["pk"])
        owner_admin = _is_owner_admin(self.request.user, obj.business_id)
        if self.request.method in SAFE_METHODS:
            if not obj.is_active and not owner_admin:
                raise Http404
            return obj
        if not owner_admin:
            raise Http404
        return obj

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ProviderListCreateView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsBusinessAdmin()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProviderCreateSerializer
        return ProviderSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role == user.Role.ADMIN:
            return Provider.objects.filter(business=user.business)
        return Provider.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.save(business=request.user.business)
        output = ProviderSerializer(provider, context=self.get_serializer_context())
        return Response(output.data, status=201)


class ProviderDetailView(generics.RetrieveUpdateAPIView):
    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsBusinessAdmin()]

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return ProviderSerializer
        return ProviderUpdateSerializer

    def get_object(self):
        obj = get_object_or_404(Provider, pk=self.kwargs["pk"])
        owner_admin = _is_owner_admin(self.request.user, obj.business_id)
        if self.request.method in SAFE_METHODS:
            if not obj.is_active and not owner_admin:
                raise Http404
            return obj
        if not owner_admin:
            raise Http404
        return obj

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(ProviderSerializer(self.get_object()).data)
