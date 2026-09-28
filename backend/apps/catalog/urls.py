from django.urls import path

from apps.scheduling import views as scheduling_views

from . import views

urlpatterns = [
    path("services/", views.ServiceListCreateView.as_view(), name="service-list-create"),
    path("services/<int:pk>/", views.ServiceDetailView.as_view(), name="service-detail"),
    path("providers/", views.ProviderListCreateView.as_view(), name="provider-list-create"),
    path("providers/<int:pk>/", views.ProviderDetailView.as_view(), name="provider-detail"),
    path(
        "providers/<int:provider_id>/working-hours/",
        scheduling_views.WorkingHoursView.as_view(),
        name="provider-working-hours",
    ),
    path(
        "providers/<int:provider_id>/time-off/",
        scheduling_views.TimeOffListCreateView.as_view(),
        name="provider-time-off-list",
    ),
    path(
        "providers/<int:provider_id>/time-off/<int:pk>/",
        scheduling_views.TimeOffDetailView.as_view(),
        name="provider-time-off-detail",
    ),
    path(
        "availability/",
        scheduling_views.AvailabilityView.as_view(),
        name="availability",
    ),
]
