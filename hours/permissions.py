from rest_framework.permissions import SAFE_METHODS, BasePermission

from hours.models import DatePeriod, Resource, Rule, TimeSpan


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS


class IsMemberOrAdminOfOrganization(BasePermission):
    def has_permission(self, request, view):
        # Create permission is checked separately in the views
        return bool(
            request.method in SAFE_METHODS
            or request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        users_organizations = request.user.get_all_organizations()

        obj_organizations = set()
        if isinstance(obj, Resource):
            obj_organizations = obj.get_organizations()

        if isinstance(obj, DatePeriod):
            obj_organizations = obj.resource.get_organizations()

        if isinstance(obj, (Rule, TimeSpan)):
            obj_organizations = obj.group.period.resource.get_organizations()

        return bool(users_organizations.intersection(obj_organizations))
