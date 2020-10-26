from django_filters import rest_framework as filters

from .models import DatePeriod, Resource, TimeSpan
from .utils import get_resource_pk_filter


class DatePeriodFilter(filters.FilterSet):
    resource = filters.CharFilter(method="resource_filter")

    class Meta:
        model = DatePeriod
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        try:
            resource = Resource.objects.get(**get_resource_pk_filter(value))
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(resource=resource)


class TimeSpanFilter(filters.FilterSet):
    resource = filters.CharFilter(method="resource_filter")

    class Meta:
        model = TimeSpan
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        try:
            resource = Resource.objects.get(**get_resource_pk_filter(value))
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(group__period__resource=resource)
