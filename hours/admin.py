from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    DataSource,
    DatePeriod,
    Resource,
    ResourceOrigin,
    Rule,
    TimeSpan,
    TimeSpanGroup,
)


class HaukiModelAdmin(SimpleHistoryAdmin, TranslationAdmin):
    pass


class ResourceOriginInline(admin.TabularInline):
    model = ResourceOrigin
    extra = 1


class ResourceAdmin(HaukiModelAdmin):
    inlines = (ResourceOriginInline,)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        if obj:
            # Remove self and parents from the children selector
            remove_ids = [obj.id]
            remove_ids.extend(obj.parents.values_list(flat=True))

            form.base_fields["children"].queryset = Resource.objects.exclude(
                pk__in=remove_ids,
            )

        return form


class TimeSpanInline(admin.StackedInline):
    model = TimeSpan
    extra = 0


class RuleInline(admin.StackedInline):
    model = Rule
    extra = 0


class TimeSpanGroupAdmin(admin.ModelAdmin):
    model = TimeSpanGroup
    list_display = (
        "get_period_name",
        "get_resource_name",
        "get_start_date",
        "get_end_date",
        "get_resource_state",
    )
    inlines = (TimeSpanInline, RuleInline)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        return qs.select_related("period", "period__resource")

    def get_period_name(self, obj):
        return obj.period.name

    get_period_name.short_description = _("Period name")

    def get_resource_name(self, obj):
        return obj.period.resource.name

    get_resource_name.short_description = _("Resource")

    def get_start_date(self, obj):
        return obj.period.start_date

    get_start_date.short_description = _("Start date")

    def get_end_date(self, obj):
        return obj.period.end_date

    get_end_date.short_description = _("End date")

    def get_resource_state(self, obj):
        return obj.period.resource_state

    get_resource_state.short_description = _("Resource state")


class DatePeriodAdmin(HaukiModelAdmin):
    list_display = ("name", "resource", "start_date", "end_date", "resource_state")


admin.site.register(DataSource, HaukiModelAdmin)
admin.site.register(Resource, ResourceAdmin)
admin.site.register(DatePeriod, DatePeriodAdmin)
admin.site.register(TimeSpanGroup, TimeSpanGroupAdmin)
