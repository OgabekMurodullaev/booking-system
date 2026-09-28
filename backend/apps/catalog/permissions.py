from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from apps.catalog.models import Provider


class IsBusinessAdminOrOwnProvider(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        provider = get_object_or_404(Provider, pk=view.kwargs["provider_id"])
        view.provider = provider

        if user.role == user.Role.ADMIN:
            return provider.business_id == user.business_id
        if user.role == user.Role.PROVIDER:
            return provider.user_id == user.id
        return False
