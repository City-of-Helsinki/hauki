import datetime
from operator import itemgetter
from typing import Tuple

import pytz
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from django_orghierarchy.models import Organization
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.fields import BooleanField, CharField, ListField
from rest_framework.filters import BaseFilterBackend, OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import clone_request
from rest_framework.response import Response

from .authentication import HaukiSignedAuthData
from .enums import State
from .filters import DatePeriodFilter, TimeSpanFilter, parse_maybe_relative_date_string
from .models import DatePeriod, Resource, Rule, TimeElement, TimeSpan
from .permissions import (
    IsMemberOrAdminOfOrganization,
    ReadOnlyPublic,
    filter_queryset_by_permission,
)
from .serializers import (
    DailyOpeningHoursSerializer,
    DatePeriodSerializer,
    IsOpenNowSerializer,
    OrganizationSerializer,
    ResourceDailyOpeningHoursSerializer,
    ResourceSerializer,
    RuleCreateSerializer,
    RuleSerializer,
    TimeSpanCreateSerializer,
    TimeSpanSerializer,
)
from .signals import DeferUpdatingDenormalizedDatePeriodData
from .utils import get_resource_pk_filter


class OnCreateOrgMembershipCheck:
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.is_superuser:
            organization = serializer.validated_data.get("organization")
            ancestry_organizations = set()
            resource = None

            if "resource" in serializer.validated_data.keys():
                resource = serializer.validated_data.get("resource")
            elif isinstance(
                serializer, (RuleCreateSerializer, TimeSpanCreateSerializer)
            ):
                time_span_group = serializer.validated_data.get("group")
                resource = time_span_group.period.resource
            if resource:
                # We are creating object related to resource.
                if not organization:
                    organization = resource.organization
                if resource.ancestry_organization:
                    ancestry_organizations = set(resource.ancestry_organization)
            else:
                # We are creating a new resource.
                if not organization:
                    organization = None
                parents = serializer.validated_data.get("parents")
                if parents:
                    resource = parents[0]
                    organization = resource.organization
                    for parent in parents:
                        ancestry_organizations.add(parent.organization.id)
                        if parent.ancestry_organization:
                            ancestry_organizations.update(parent.ancestry_organization)

            if not organization and not ancestry_organizations:
                raise ValidationError(
                    detail=_(
                        "Cannot create or edit resources that "
                        "are not part of an organization "
                    )
                )
            else:
                users_organizations = request.user.get_all_organizations()
                auth = request.auth
                if (
                    isinstance(auth, HaukiSignedAuthData)
                    and auth.resource
                    and auth.resource == resource
                ):
                    # A special case for users signed in using the
                    # HaukiSignedAuthentication
                    pass
                elif (
                    not ancestry_organizations
                    and organization not in users_organizations
                ) or (
                    ancestry_organizations
                    and set(ancestry_organizations).difference(
                        [uo.id for uo in users_organizations]
                    )
                ):
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
    @extend_schema(
        summary="Check method permission for object",
        request=inline_serializer("", {}),
        responses=inline_serializer(
            "permission_check", {"has_permission": BooleanField()}
        ),
    )
    @action(
        detail=True,
        methods=["get", "post", "put", "patch", "delete"],
        permission_classes=[],
    )
    def permission_check(self, request, pk=None):
        """Runs check_object_permission for the object with the used method and returns
        the result"""
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
        raise ValidationError(
            detail=_("start_date and end_date GET parameters are required")
        )

    try:
        start_date = parse_maybe_relative_date_string(
            request.query_params.get("start_date", "")
        )
    except ValueError:
        raise ValidationError(detail=_("Invalid start_date"))

    try:
        end_date = parse_maybe_relative_date_string(
            request.query_params.get("end_date", ""), end_date=True
        )
    except ValueError:
        raise ValidationError(detail=_("Invalid end_date"))

    if start_date > end_date:
        raise ValidationError(detail=_("start_date must be before end_date"))

    return start_date, end_date


class ResourceFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        data_source = request.query_params.get("data_source", None)
        origin_id_exists = request.query_params.get("origin_id_exists", None)
        parent = request.query_params.get("parent", None)
        child = request.query_params.get("child", None)
        date_periods_hash = request.query_params.get("date_periods_hash", None)

        filter_q = Q()
        if data_source is not None:
            filter_q = Q(origins__data_source=data_source) | Q(
                ancestry_data_source__contains=[data_source]
            )

        if parent is not None:
            filter_q &= Q(parents__id=parent)

        if child is not None:
            filter_q &= Q(children__id=child)

        if origin_id_exists is not None and origin_id_exists:
            origin_id_exists = origin_id_exists.lower() == "true"

            if origin_id_exists or not data_source:
                # Keep all resources that don't have any origin ids
                # (when origin_id_exists=True)
                # or Don't have origin id in any data source.
                # (when data_source=None and origin_id_exists=False)
                filter_q &= Q(origins__origin_id__isnull=not origin_id_exists)
            else:
                # Exclude resources that have origin id in the provided
                # data source
                return queryset.filter(filter_q).exclude(
                    Q(origins__data_source=data_source)
                    & Q(origins__origin_id__isnull=False)
                )

        if date_periods_hash is not None:
            filter_q &= Q(date_periods_hash=date_periods_hash)

        return queryset.filter(filter_q)


@extend_schema_view(
    list=extend_schema(
        summary="List Resources",
        parameters=[
            OpenApiParameter(
                "data_source",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by data source",
            ),
            OpenApiParameter(
                "origin_id_exists",
                OpenApiTypes.BOOL,
                OpenApiParameter.QUERY,
                description="Filter by existing/missing origin_id",
            ),
            OpenApiParameter(
                "parent",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by parent id",
            ),
            OpenApiParameter(
                "child",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by child id",
            ),
        ],
    ),
    create=extend_schema(summary="Create a Resource"),
    retrieve=extend_schema(summary="Find Resource by ID"),
    update=extend_schema(summary="Update existing Resource"),
    partial_update=extend_schema(summary="Update existing Resource partially"),
    destroy=extend_schema(summary="Delete existing Resource"),
    opening_hours=extend_schema(
        summary="Get opening hours for Resource",
        parameters=[
            OpenApiParameter(
                "start_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="First date to return hours for",
            ),
            OpenApiParameter(
                "end_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Last date to return hours for",
            ),
        ],
        responses=DailyOpeningHoursSerializer,
    ),
    is_open_now=extend_schema(
        summary="Is Resource open now?", responses=IsOpenNowSerializer
    ),
    copy_date_periods=extend_schema(
        summary="Copy all the periods from this resource to other resources",
        request=OpenApiTypes.NONE,
        parameters=[
            OpenApiParameter(
                "target_resources",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="Comma separated list of target resource ids",
            ),
            OpenApiParameter(
                "replace",
                OpenApiTypes.BOOL,
                OpenApiParameter.QUERY,
                description="Replace all the periods in the target resource",
                default=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Copy succeeded",
            ),
            400: OpenApiResponse(description="Bad request"),
            403: OpenApiResponse(
                description="No permission read source resource or no permission"
                " to modify one or more of the target resources"
            ),
            404: OpenApiResponse(description="One or more target resources not found"),
        },
    ),
)
class ResourceViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    serializer_class = ResourceSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    pagination_class = PageSizePageNumberPagination
    filter_backends = (DjangoFilterBackend, ResourceFilterBackend, OrderingFilter)

    def get_queryset(self):
        queryset = (
            Resource.objects.prefetch_related(
                "origins", "children", "parents", "origins__data_source"
            )
            .distinct()
            .order_by("id")
        )

        # Filter the queryset according to read permissions
        queryset = filter_queryset_by_permission(
            self.request.user, queryset, auth=self.request.auth
        )

        return queryset

    def get_object(self, check_permission=True):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs.get(lookup_url_kwarg, None)
        if not pk:
            raise Http404

        obj = get_object_or_404(queryset, **get_resource_pk_filter(pk))

        if check_permission:
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

    @action(detail=True)
    def is_open_now(self, request, pk=None):
        resource = self.get_object()
        open_states = State.open_states()
        time_now = timezone.now()

        tz = resource.timezone
        if not tz:
            tz = pytz.timezone(settings.RESOURCE_DEFAULT_TIMEZONE)
            if not tz:
                tz = pytz.timezone("Europe/Helsinki")

        resource_time_now = time_now.astimezone(tz)

        other_tz = None
        if request.query_params.get("timezone"):
            try:
                other_tz = pytz.timezone(request.query_params.get("timezone"))
            except pytz.exceptions.UnknownTimeZoneError:
                raise APIException("Unknown timezone")

        opening_hours = resource.get_daily_opening_hours(
            resource_time_now.date(), resource_time_now.date()
        ).get(
            datetime.date(
                year=resource_time_now.year,
                month=resource_time_now.month,
                day=resource_time_now.day,
            ),
            [],
        )

        matching_opening_hours = []
        matching_opening_hours_other_tz = []

        for opening_hour in opening_hours:
            start_date = resource_time_now.date()
            end_date = resource_time_now.date()
            if opening_hour.end_time_on_next_day:
                end_date = resource_time_now.date() + relativedelta(days=1)
            start_time = (
                opening_hour.start_time
                if opening_hour.start_time
                else datetime.time.min
            )
            end_time = (
                opening_hour.end_time if opening_hour.end_time else datetime.time.max
            )

            start_datetime = tz.localize(
                datetime.datetime(
                    year=start_date.year,
                    month=start_date.month,
                    day=start_date.day,
                    hour=start_time.hour,
                    minute=start_time.minute,
                    second=start_time.second,
                )
            )

            end_datetime = tz.localize(
                datetime.datetime(
                    year=end_date.year,
                    month=end_date.month,
                    day=end_date.day,
                    hour=end_time.hour,
                    minute=end_time.minute,
                    second=end_time.second,
                )
            )

            if (
                start_datetime <= resource_time_now <= end_datetime
                and opening_hour.resource_state in open_states
            ):
                matching_opening_hours.append(opening_hour)
                if not other_tz:
                    continue

                other_timezone_start_datetime = start_datetime.astimezone(other_tz)
                other_timezone_end_datetime = end_datetime.astimezone(other_tz)

                matching_opening_hours_other_tz.append(
                    TimeElement(
                        start_time=other_timezone_start_datetime.time(),
                        end_time=other_timezone_end_datetime.time(),
                        end_time_on_next_day=other_timezone_start_datetime.date()
                        != other_timezone_end_datetime.date(),
                        resource_state=opening_hour.resource_state,
                        override=opening_hour.override,
                        full_day=opening_hour.full_day,
                        name=opening_hour.name,
                        description=opening_hour.description,
                        periods=opening_hour.periods,
                    )
                )

        other_timezone_time_now = resource_time_now.astimezone(other_tz)

        data = {
            "is_open": bool(matching_opening_hours),
            "resource_timezone": tz,
            "resource_time_now": resource_time_now,
            "matching_opening_hours": matching_opening_hours,
            "resource": resource,
        }

        if other_tz:
            data = {
                **data,
                "other_timezone": other_tz,
                "other_timezone_time_now": other_timezone_time_now,
                "matching_opening_hours_in_other_tz": matching_opening_hours_other_tz,
            }

        serializer = IsOpenNowSerializer(data)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def copy_date_periods(self, request, pk=None):
        resource = self.get_object(check_permission=False)

        # The user only needs read permission to the source resource
        self.check_object_permissions(clone_request(self.request, "GET"), resource)

        if not request.query_params.get("target_resources"):
            raise ValidationError(detail=_("target_resources parameter is required"))

        replace = False
        if request.query_params.get("replace"):
            replace_value = request.query_params.get("replace").lower().strip()
            if replace_value in ["1", "true", "yes"]:
                replace = True

        target_resource_ids = [
            resource_id.strip()
            for resource_id in request.query_params.get("target_resources", "").split(
                ","
            )
            if resource_id.strip()
        ]

        target_resources = []
        no_permission_resource_ids = []
        for target_resource_id in target_resource_ids:
            try:
                target_resource = Resource.objects.get(
                    **get_resource_pk_filter(target_resource_id)
                )
            except Resource.DoesNotExist:
                detail = _('Resource with the id "{}" not found.').format(
                    target_resource_id
                )
                raise NotFound(detail=detail)

            if target_resource.id == resource.id:
                detail = _("Can't copy date periods to self").format(target_resource_id)
                raise APIException(detail=detail)

            try:
                self.check_object_permissions(self.request, target_resource)
            except PermissionDenied:
                no_permission_resource_ids.append(target_resource_id)
                continue

            target_resources.append(target_resource)

        if no_permission_resource_ids:
            detail = _("No permission to modify resource(s): {}").format(
                ", ".join(no_permission_resource_ids)
            )
            raise PermissionDenied(detail=detail)

        with transaction.atomic():
            with DeferUpdatingDenormalizedDatePeriodData():
                for target_resource in target_resources:
                    resource.copy_all_periods_to_resource(
                        target_resource, replace=replace
                    )

        return Response(
            {
                "message": "Date periods copied",
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="List Date Periods",
        parameters=[
            OpenApiParameter(
                "resource",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by resource id or multiple resource ids (comma-separated)",  # noqa
            ),
            OpenApiParameter(
                "end_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by exact period end date",
            ),
            OpenApiParameter(
                "end_date_gte",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by end date greater than given date (or null)",
            ),
            OpenApiParameter(
                "end_date_lte",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by end date less than given date",
            ),
            OpenApiParameter(
                "start_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by exact period start date",
            ),
            OpenApiParameter(
                "start_date_gte",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by start date greater than given date",
            ),
            OpenApiParameter(
                "start_date_lte",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Filter by start date less than given date (or null",
            ),
        ],
    ),
    create=extend_schema(summary="Create a Date Period"),
    retrieve=extend_schema(summary="Find Date Period by ID"),
    update=extend_schema(summary="Update existing Date Period"),
    partial_update=extend_schema(summary="Update existing Date Period partially"),
    destroy=extend_schema(summary="Delete existing Date Period"),
)
class DatePeriodViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    serializer_class = DatePeriodSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    filterset_class = DatePeriodFilter
    filter_backends = (DjangoFilterBackend, OrderingFilter)

    def get_queryset(self):
        queryset = DatePeriod.objects.prefetch_related(
            "origins",
            "origins__data_source",
            "time_span_groups",
            "time_span_groups__time_spans",
            "time_span_groups__rules",
        ).order_by("start_date", "end_date")

        # Filter the queryset according to read permissions
        queryset = filter_queryset_by_permission(
            self.request.user, queryset, auth=self.request.auth
        )

        return queryset

    def list(self, request, *args, **kwargs):
        if (
            not request.query_params.get("resource")
            and not request.query_params.get("start_date")
            and not request.query_params.get("start_date_lte")
            and not request.query_params.get("start_date_gte")
            and not request.query_params.get("end_date")
            and not request.query_params.get("end_date")
            and not request.query_params.get("end_date_lte")
            and not request.query_params.get("end_date_gte")
        ):
            raise ValidationError(
                detail=_(
                    "resource, start_date or end_date GET parameter is required to"
                    "list date periods"
                )
            )
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(summary="List Rules"),
    create=extend_schema(summary="Create a Rule"),
    retrieve=extend_schema(summary="Find Rule by ID"),
    update=extend_schema(summary="Update existing Rule"),
    partial_update=extend_schema(summary="Update existing Rule partially"),
    destroy=extend_schema(summary="Delete existing Rule"),
)
class RuleViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    serializer_class = RuleSerializer
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    filter_backends = (DjangoFilterBackend, OrderingFilter)

    def get_queryset(self):
        queryset = (
            Rule.objects.all()
            .select_related("group", "group__period")
            .order_by("group__period__start_date", "group__period__end_date")
        )

        # Filter the queryset according to read permissions
        queryset = filter_queryset_by_permission(
            self.request.user, queryset, auth=self.request.auth
        )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return RuleCreateSerializer

        return RuleSerializer

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("resource"):
            raise ValidationError(
                detail=_(
                    "resource GET parameter is required to list rules of resources"
                )
            )
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(summary="List Time Spans"),
    create=extend_schema(summary="Create a Time Span"),
    retrieve=extend_schema(summary="Find Time Span by ID"),
    update=extend_schema(summary="Update existing Time Span"),
    partial_update=extend_schema(summary="Update existing Time Span partially"),
    destroy=extend_schema(summary="Delete existing Time Span"),
)
class TimeSpanViewSet(
    OnCreateOrgMembershipCheck, PermissionCheckAction, viewsets.ModelViewSet
):
    serializer_class = TimeSpanSerializer
    filterset_class = TimeSpanFilter
    permission_classes = [ReadOnlyPublic | IsMemberOrAdminOfOrganization]
    filter_backends = (DjangoFilterBackend, OrderingFilter)

    def get_queryset(self):
        queryset = TimeSpan.objects.all()

        # Filter the queryset according to read permissions
        queryset = filter_queryset_by_permission(
            self.request.user, queryset, auth=self.request.auth
        )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return TimeSpanCreateSerializer

        return TimeSpanSerializer

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("resource"):
            raise ValidationError(
                detail=_(
                    "resource GET parameter is required to list time spans of resources"
                )
            )
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(summary="List Organizations"),
    retrieve=extend_schema(summary="Find Organizations by ID"),
)
class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.select_related("parent").prefetch_related(
        "children"
    )
    serializer_class = OrganizationSerializer
    filterset_fields = ["parent"]
    filter_backends = (DjangoFilterBackend, OrderingFilter)


class AuthRequiredTestView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Authentication test",
        description="Can be used to see if the current request is authenticated. "
        "Handy for testing HaukiSignedAuth links.",
        responses=inline_serializer(
            "auth_required_test",
            {
                "message": CharField(),
                "username": CharField(),
                "organization_ids": ListField(),
            },
        ),
    )
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
        resource = request.query_params.get("resource", None)

        if data_source is not None:
            queryset = queryset.filter(
                Q(origins__data_source=data_source)
                | Q(ancestry_data_source__contains=[data_source])
            )
        if resource is not None:
            filters = map(get_resource_pk_filter, resource.split(","))
            q_objects = [Q(**filter) for filter in filters]
            query_q = Q()
            for q in q_objects:
                query_q |= q
            try:
                queryset = queryset.filter(query_q)
            except (ValueError, Resource.DoesNotExist):
                pass

        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="List opening hours",
        parameters=[
            OpenApiParameter(
                "data_source",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by resource data source",
            ),
            OpenApiParameter(
                "resource",
                OpenApiTypes.UUID,
                OpenApiParameter.QUERY,
                description="Filter by resource id or multiple resource ids (comma-separated)",  # noqa
            ),
            OpenApiParameter(
                "start_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="First date to return hours for",
            ),
            OpenApiParameter(
                "end_date",
                OpenApiTypes.DATE,
                OpenApiParameter.QUERY,
                description="Last date to return hours for",
            ),
        ],
    ),
)
class OpeningHoursViewSet(viewsets.GenericViewSet):
    filter_backends = (DjangoFilterBackend, OpeningHoursFilterBackend, OrderingFilter)
    serializer_class = ResourceDailyOpeningHoursSerializer
    pagination_class = PageSizePageNumberPagination

    def get_queryset(self):
        queryset = (
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
            .distinct()
            .order_by("id")
        )

        # Filter the queryset according to read permissions
        queryset = filter_queryset_by_permission(
            self.request.user, queryset, auth=self.request.auth
        )

        return queryset

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
