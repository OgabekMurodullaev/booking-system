import django_filters

from .models import Booking


class BookingFilterSet(django_filters.FilterSet):
    date_from = django_filters.DateFilter(method="filter_date_from")
    date_to = django_filters.DateFilter(method="filter_date_to")

    class Meta:
        model = Booking
        fields = ["status", "provider", "service"]

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(time_range__startswith__date__gte=value)

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(time_range__startswith__date__lte=value)
