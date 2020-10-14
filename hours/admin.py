from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import DataSource, DatePeriod, OpeningHours, Resource, ResourceOrigin, Rule


class HaukiModelAdmin(SimpleHistoryAdmin, TranslationAdmin):
    pass


class ResourceOriginInline(admin.TabularInline):
    model = ResourceOrigin


class ResourceAdmin(HaukiModelAdmin):
    inlines = (ResourceOriginInline,)


class OpeningHoursInline(admin.StackedInline):
    model = OpeningHours
    extra = 0


class RuleInline(admin.StackedInline):
    model = Rule
    extra = 0


class DatePeriodAdmin(HaukiModelAdmin):
    list_display = ("name", "resource", "start_date", "end_date", "period_type")
    inlines = (OpeningHoursInline, RuleInline)


admin.site.register(DataSource, HaukiModelAdmin)
admin.site.register(Resource, ResourceAdmin)
admin.site.register(DatePeriod, DatePeriodAdmin)
# admin.site.register(OpeningHours, HaukiModelAdmin)
# admin.site.register(Rule, HaukiModelAdmin)
