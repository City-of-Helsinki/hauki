from django.http import Http404
from rest_framework import viewsets
from rest_framework.generics import get_object_or_404

from .models import DatePeriod, OpeningHours, Resource, Rule
from .serializers import (
    DatePeriodSerializer,
    OpeningHoursSerializer,
    ResourceSerializer,
    RuleSerializer,
)


class ResourceViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceSerializer

    def get_queryset(self):
        return Resource.objects.all().order_by("id")

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs.get(lookup_url_kwarg, None)
        if not pk:
            raise Http404

        if ":" in pk:
            # Find the object using resource origin
            data_source_id, origin_id = pk.split(":")
            filter_kwargs = {
                "resourceorigin__data_source_id": data_source_id,
                "resourceorigin__origin_id": origin_id,
            }
        else:
            filter_kwargs = {self.lookup_field: pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj


class DatePeriodViewSet(viewsets.ModelViewSet):
    queryset = DatePeriod.objects.all().order_by("start_date", "end_date")
    serializer_class = DatePeriodSerializer


class RuleViewSet(viewsets.ModelViewSet):
    queryset = (
        Rule.objects.all()
        .select_related("period")
        .order_by("period__start_date", "period__end_date")
    )
    serializer_class = RuleSerializer


class OpeningHoursViewSet(viewsets.ModelViewSet):
    queryset = OpeningHours.objects.all()
    serializer_class = OpeningHoursSerializer
