from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from hours.models import DatePeriod, Resource, Rule, TimeSpan


def filter_queryset_by_permission(request, queryset):
    """
    Returns the queryset filtered by permission of request. Returned queryset
    only contains objects of organizations the request has rights to.

    Resource parents and their parents organizations, if present, override
    access to a child resource. Similarly, parent publicity is a requirement
    for resource publicity.
    """
    if request.user.is_superuser:
        return queryset
    if request.user and request.user.is_authenticated:
        users_organizations = request.user.get_all_organizations()
    else:
        users_organizations = set()

    if queryset.model == Resource:
        children_to_check = queryset
        path_to_resource = ""
    elif queryset.model == DatePeriod:
        children_to_check = Resource.objects.filter(date_periods__in=queryset)
        path_to_resource = "resource__"
    elif queryset.model == Rule:
        children_to_check = Resource.objects.filter(
            date_periods__time_span_groups__rules__in=queryset
        )
        path_to_resource = "group__period__resource__"
    elif queryset.model == TimeSpan:
        children_to_check = Resource.objects.filter(
            date_periods__time_span_groups__time_spans__in=queryset
        )
        path_to_resource = "group__period__resource__"
    else:
        raise Exception("Permissions not defined for model %s" % queryset.model)

    # if a resource has no parents, publicity and organization check is easy
    is_public = Q(**{path_to_resource + "is_public": True})
    has_request_organization = Q(**{path_to_resource + "parents__isnull": True}) & Q(
        **{path_to_resource + "organization__in": users_organizations}
    )

    # if a resource has parents, parents determine organizations that have rights
    # and publicity
    parents = Resource.objects.filter(children__in=children_to_check)
    # multiple levels of parents will make the check slightly more complex
    while parents:
        has_request_organization |= Q(
            **{path_to_resource + "parents__organization__in": users_organizations}
        )
        is_public &= Q(**{path_to_resource + "parents__isnull": True}) | Q(
            **{path_to_resource + "parents__is_public": True}
        )
        parents = Resource.objects.filter(children__in=parents)
        path_to_resource += "parents__"

    if request.method in SAFE_METHODS:
        return queryset.filter(is_public | has_request_organization).distinct()
    return queryset.filter(has_request_organization).distinct()


class ReadOnlyPublic(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        return bool(
            filter_queryset_by_permission(request, type(obj).objects.filter(id=obj.id))
        )


class IsMemberOrAdminOfOrganization(BasePermission):
    def has_permission(self, request, view):
        # Create permission is checked separately in the views
        return bool(
            request.method in SAFE_METHODS
            or request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        return bool(
            filter_queryset_by_permission(request, type(obj).objects.filter(id=obj.id))
        )
