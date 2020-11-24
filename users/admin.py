from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User


class HaukiUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


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


admin.site.register(User, HaukiUserAdmin)
