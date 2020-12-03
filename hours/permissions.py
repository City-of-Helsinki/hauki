from functools import reduce

from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from hours.models import DatePeriod, Resource, Rule, TimeSpan


def deep_getattr(obj, attrs):
    return reduce(lambda o, key: getattr(o, key), attrs.split("__"), obj)


def get_path_to_resource(klass):
    if klass == Resource:
        return ""
    elif klass == DatePeriod:
        return "resource__"
    elif klass == Rule:
        return "group__period__resource__"
    elif klass == TimeSpan:
        return "group__period__resource__"

    return None


def filter_queryset_by_permission(user, queryset):
    """Returns the queryset filtered by permission of the request

    Returned queryset contains only objects of organizations the request has rights to.

    Resource parents and their parents organizations, if present, override
    access to a child resource. Similarly, parent publicity is a requirement
    for resource publicity.
    """
    if user.is_superuser:
        return queryset

    if user and user.is_authenticated:
        users_organizations = user.get_all_organizations()
    else:
        users_organizations = set()

    path_to_resource = get_path_to_resource(queryset.model)

    if path_to_resource is None:
        raise NotImplementedError(
            "Permissions not defined for class {0}".format(queryset.model)
        )

    is_public = Q(**{path_to_resource + "is_public": True}) & (
        Q(**{path_to_resource + "ancestry_is_public__isnull": True})
        | Q(**{path_to_resource + "ancestry_is_public": True})
    )

    has_request_organization = (
        Q(**{path_to_resource + "organization__in": users_organizations})
        & Q(**{path_to_resource + "ancestry_organization__isnull": True})
    ) | (
        Q(
            **{
                path_to_resource
                + "ancestry_organization__overlap": [o.id for o in users_organizations]
            }
        )
    )

    return queryset.filter(is_public | has_request_organization)


class ReadOnlyPublic(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method not in SAFE_METHODS:
            return False

        if request.user.is_superuser:
            return True

        if request.user and request.user.is_authenticated:
            users_organizations = request.user.get_all_organizations()
        else:
            users_organizations = set()

        path_to_resource = get_path_to_resource(obj.__class__)

        if path_to_resource is None:
            raise NotImplementedError(
                "Permissions not defined for class {0}".format(obj.__class__)
            )

        resource_is_public = deep_getattr(obj, path_to_resource + "is_public")
        resource_ancestry_is_public = deep_getattr(
            obj, path_to_resource + "ancestry_is_public"
        )
        resource_organization = deep_getattr(obj, path_to_resource + "organization")
        resource_ancestry_organization = deep_getattr(
            obj, path_to_resource + "ancestry_organization"
        )

        if resource_is_public and (
            resource_ancestry_is_public is None or resource_ancestry_is_public
        ):
            return True

        if (
            resource_organization in users_organizations
            and not resource_ancestry_organization
        ) or (
            resource_ancestry_organization
            and users_organizations.intersection(resource_ancestry_organization)
        ):
            return True

        return False


class IsMemberOrAdminOfOrganization(BasePermission):
    def has_permission(self, request, view):
        # Create permission is checked separately in the views
        return bool(
            request.method in SAFE_METHODS
            or request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        if request.user and request.user.is_authenticated:
            users_organizations = request.user.get_all_organizations()
        else:
            users_organizations = set()

        path_to_resource = get_path_to_resource(obj.__class__)

        if path_to_resource is None:
            raise NotImplementedError(
                "Permissions not defined for class {0}".format(obj.__class__)
            )

        resource_organization = deep_getattr(obj, path_to_resource + "organization")
        resource_ancestry_organization = deep_getattr(
            obj, path_to_resource + "ancestry_organization"
        )

        if (
            resource_organization in users_organizations
            and not resource_ancestry_organization
        ) or (
            resource_ancestry_organization
            and users_organizations.intersection(resource_ancestry_organization)
        ):
            return True

        return False
