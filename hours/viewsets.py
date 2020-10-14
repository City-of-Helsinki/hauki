from rest_framework import viewsets

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
