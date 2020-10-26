from django.http import Http404
from django_orghierarchy.models import Organization
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .authentication import HaukiSignedAuthentication
from .models import DatePeriod, OpeningHours, Resource, Rule
from .serializers import (
    DatePeriodSerializer,
    OpeningHoursSerializer,
    OrganizationSerializer,
    ResourceSerializer,
    RuleSerializer,
)
from .utils import get_resource_pk_filter


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

        obj = get_object_or_404(queryset, **get_resource_pk_filter(pk))

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


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    filterset_fields = ["parent"]


class AuthRequiredTestView(viewsets.ViewSet):
    authentication_classes = [HaukiSignedAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        organization_ids = set()
        organization_ids.update(
            request.user.admin_organizations.values_list("id", flat=True)
        )
        organization_ids.update(
            request.user.organization_memberships.values_list("id", flat=True)
        )

        return Response(
            {
                "message": "You are authenticated",
                "username": request.user.username,
                "organization_ids": organization_ids,
            }
        )
