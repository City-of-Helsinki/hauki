from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization

from .models import User, UserOrigin


class HaukiUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class UserOriginInline(admin.TabularInline):
    model = UserOrigin
    extra = 1


class AdminOrganizationsInline(admin.TabularInline):
    model = Organization.admin_users.through
    extra = 0


class OrganizationMembershipsInline(admin.TabularInline):
    model = Organization.regular_users.through
    extra = 0


class HaukiUserAdmin(UserAdmin):
    model = User
    form = HaukiUserChangeForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (_("Helusers"), {"fields": ("uuid", "department_name", "ad_groups")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    inlines = (
        UserOriginInline,
        AdminOrganizationsInline,
        OrganizationMembershipsInline,
    )


admin.site.register(User, HaukiUserAdmin)
