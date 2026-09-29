from django.urls import path

from . import views

urlpatterns = [
    path("", views.BookingListCreateView.as_view(), name="booking-list-create"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/submit/", views.BookingSubmitView.as_view(), name="booking-submit"),
    path("<int:pk>/confirm/", views.BookingConfirmView.as_view(), name="booking-confirm"),
    path("<int:pk>/cancel/", views.BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:pk>/complete/", views.BookingCompleteView.as_view(), name="booking-complete"),
    path("<int:pk>/calendar.ics", views.BookingCalendarView.as_view(), name="booking-calendar"),
]
