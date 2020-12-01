import datetime
from operator import itemgetter
from typing import Tuple

from django.db.models import Exists, OuterRef
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from django_orghierarchy.models import Organization
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from .filters import DatePeriodFilter, TimeSpanFilter, parse_maybe_relative_date_string
from .models import DatePeriod, Resource, Rule, TimeSpan
from .permissions import (
    IsMemberOrAdminOfOrganization,
    ReadOnlyPublic,
    filter_queryset_by_permission,
)
from .serializers import (
    DailyOpeningHoursSerializer,
    DatePeriodSerializer,
    OrganizationSerializer,
    ResourceDailyOpeningHoursSerializer,
    ResourceSerializer,
    RuleCreateSerializer,
    RuleSerializer,
    TimeSpanCreateSerializer,
    TimeSpanSerializer,
)
from .utils import get_resource_pk_filter


class OnCreateOrgMembershipCheck:
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.is_superuser:
            organization = serializer.validated_data.get("organization")

            if not organization:
                if "resource" in serializer.validated_data.keys():
                    resource = serializer.validated_data.get("resource")
                    if resource:
                        organization = resource.organization

                if isinstance(
                    serializer, (RuleCreateSerializer, TimeSpanCreateSerializer)
                ):
                    time_span_group = serializer.validated_data.get("group")
                    organization = time_span_group.period.resource.organization

            if not organization:
                raise ValidationError(
                    detail=_(
                        "Cannot create or edit resources that "
                        "are not part of an organization "
                    )
                )
            else:
                users_organizations = request.user.get_all_organizations()
                if organization not in users_organizations:
                    raise PermissionDenied(
                        detail=_(
                            "Cannot add data to organizations the user "
                            "is not a member of"
                        )
                    )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class PermissionCheckAction:
    @action(
        detail=True,
        methods=["get", "post", "put", "patch", "delete"],
        permission_classes=[],
    )
    def permission_check(self, request, pk=None):
        """Runs check_object_permission for the object and returns the result"""
        obj = self.get_object()

        # This action should be callable without any permissions, but the
        # check_object_permissions call should use the original permissions
        # from the viewset.
        old_permission_classes = self.permission_classes
        self.permission_classes = self.__class__.permission_classes

        try:
            self.check_object_permissions(request, obj)
            has_permission = True
        except APIException:
            has_permission = False

        self.permission_classes = old_permission_classes

        return Response({"has_permission": has_permission})


class PageSizePageNumberPagination(PageNumberPagination):
    page_size = 100
    max_page_size = 1000
    page_size_query_param = "page_size"


def get_start_and_end_from_params(request) -> Tuple[datetime.date, datetime.date]:
    if not request.query_params.get("start_date") or not request.query_params.get(
        "end_date"
    ):
        raise APIException("start_date and end_date GET parameters are required")

    try:
        start_date = parse_maybe_relative_date_string(
            request.query_params.get("start_date", "")
        )
    except ValueError:
        raise APIException("Invalid start_date")

    try:
        end_date = parse_maybe_relative_date_string(
            request.query_params.get("end_date", ""), end_date=True
        )
    except ValueError:
        raise APIException("Invalid end_date")

    if start_date > end_date:
        raise APIException("start_date must be before end_date")

    return start_date, end_date


class ResourceViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    serializer_class = ResourceSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    pagination_class = PageSizePageNumberPagination

    def get_queryset(self):
        queryset = Resource.objects.prefetch_related(
            "origins", "children", "parents", "origins__data_source"
        ).order_by("id")
        # Object permissions are not checked in listings, so we have
        # to filter the queryset according to permissions.
        if self.request.method in SAFE_METHODS:
            queryset = filter_queryset_by_permission(self.request, queryset)
        return queryset

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

    @action(detail=True)
    def opening_hours(self, request, pk=None):
        resource = self.get_object()

        (start_date, end_date) = get_start_and_end_from_params(request)

        opening_hours = resource.get_daily_opening_hours(start_date, end_date)

        opening_hours_list = []
        for the_date, time_elements in opening_hours.items():
            opening_hours_list.append(
                {
                    "date": the_date,
                    "times": time_elements,
                }
            )
        opening_hours_list.sort(key=itemgetter("date"))

        serializer = DailyOpeningHoursSerializer(opening_hours_list, many=True)

        return Response(serializer.data)


class DatePeriodViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    queryset = DatePeriod.objects.prefetch_related(
        "time_span_groups", "time_span_groups__time_spans", "time_span_groups__rules"
    ).order_by("start_date", "end_date")
    serializer_class = DatePeriodSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    filterset_class = DatePeriodFilter


class RuleViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    queryset = (
        Rule.objects.all()
        .select_related("group", "group__period")
        .order_by("group__period__start_date", "group__period__end_date")
    )
    serializer_class = RuleSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]

    def get_serializer_class(self):
        if self.action == "create":
            return RuleCreateSerializer

        return RuleSerializer


class TimeSpanViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    queryset = TimeSpan.objects.all()
    serializer_class = TimeSpanSerializer
    filterset_class = TimeSpanFilter
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]

    def get_serializer_class(self):
        if self.action == "create":
            return TimeSpanCreateSerializer

        return TimeSpanSerializer


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    filterset_fields = ["parent"]


class AuthRequiredTestView(viewsets.ViewSet):
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


class OpeningHoursFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        data_source = request.query_params.get("data_source", None)

        if data_source is not None:
            queryset = queryset.filter(origins__data_source=data_source)

        return queryset


class OpeningHoursViewSet(viewsets.GenericViewSet):
    filter_backends = (DjangoFilterBackend, OpeningHoursFilterBackend)
    serializer_class = ResourceDailyOpeningHoursSerializer
    pagination_class = PageSizePageNumberPagination

    def get_queryset(self):
        # TODO: is_public check
        return (
            Resource.objects.filter(
                # Query only resources that have date periods
                Exists(DatePeriod.objects.filter(resource=OuterRef("pk")))
            )
            .prefetch_related(
                "origins",
                "origins__data_source",
                "date_periods",
                "date_periods__time_span_groups",
                "date_periods__time_span_groups__time_spans",
                "date_periods__time_span_groups__rules",
            )
            .order_by("id")
        )

    def list(self, request, *args, **kwargs):
        # TODO: Maybe disallow listing all of the resources and require
        #       data_source or possibly some other filter.
        queryset = self.filter_queryset(self.get_queryset())

        (start_date, end_date) = get_start_and_end_from_params(request)

        page = self.paginate_queryset(queryset)

        results = []
        for resource in page:
            processed_opening_hours = resource.get_daily_opening_hours(
                start_date, end_date
            )

            opening_hours_list = []
            for the_date, time_elements in processed_opening_hours.items():
                opening_hours_list.append(
                    {
                        "date": the_date,
                        "times": time_elements,
                    }
                )

            opening_hours_list.sort(key=itemgetter("date"))

            results.append({"resource": resource, "opening_hours": opening_hours_list})

        serializer = self.get_serializer(results, many=True)

        return self.get_paginated_response(serializer.data)
