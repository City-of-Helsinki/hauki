from functools import reduce

from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from hours.authentication import HaukiSignedAuthData
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


def filter_queryset_by_permission(user, queryset, auth=None):
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

    # A special case for users signed in using the HaukiSignedAuthentication
    is_resource = Q()
    if auth and isinstance(auth, HaukiSignedAuthData):
        if auth.resource:
            is_resource = Q(
                **{path_to_resource if path_to_resource else "id": auth.resource.id}
            ) | Q(
                # TODO: This supports only parents, not grandparents!
                **{path_to_resource + "parents": auth.resource.id}
            )

        if not auth.has_organization_rights:
            has_request_organization = Q()

    return queryset.filter(is_public | has_request_organization | is_resource)


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

        path_to_resource = get_path_to_resource(obj.__class__)

        if path_to_resource is None:
            raise NotImplementedError(
                "Permissions not defined for class {0}".format(obj.__class__)
            )

        if path_to_resource == "":
            resource = obj
        else:
            resource = deep_getattr(obj, path_to_resource.rstrip("_"))

        # A special case for users signed in using the HaukiSignedAuthentication
        if request.auth and isinstance(request.auth, HaukiSignedAuthData):
            resource_ancestors = resource.get_ancestors()
            authorized_resource = request.auth.resource
            if authorized_resource:
                #             authorized_resource
                #                      |
                #                      |
                #                      |
                #    parent A       parent B
                # not authorized   authorized
                #        |             |
                #        +------+------+
                #               |
                #           resource
                authorized_ancestors = authorized_resource.get_ancestors()
                authorized_descendants = authorized_resource.get_descendants()
                if (resource in {authorized_resource} | authorized_descendants) and (
                    not resource_ancestors.difference(
                        authorized_ancestors
                        | {authorized_resource}
                        | authorized_descendants
                    )
                ):
                    # Resource authorization allowed only if no extra parents found
                    # in the ancestor chain
                    return True

            if not request.auth.has_organization_rights:
                return False

        if request.user and request.user.is_authenticated:
            users_organizations = request.user.get_all_organizations()
        else:
            users_organizations = set()

        resource_organization = deep_getattr(obj, path_to_resource + "organization")
        resource_ancestry_organization = deep_getattr(
            obj, path_to_resource + "ancestry_organization"
        )

        if (
            not resource_ancestry_organization
            and resource_organization in users_organizations
        ) or (
            resource_ancestry_organization
            and not set(resource_ancestry_organization).difference(
                [uo.id for uo in users_organizations]
            )
        ):
            return True

        return False
