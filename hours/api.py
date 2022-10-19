from rest_framework import routers

from hours.viewsets import (
    AuthRequiredTestView,
    DatePeriodsAsTextForTprek,
    DatePeriodViewSet,
    OpeningHoursViewSet,
    OrganizationViewSet,
    ResourceViewSet,
    RuleViewSet,
    TimeSpanViewSet,
)

all_views = []


def register_view(klass, name, basename=None):
    entry = {"class": klass, "name": name}
    if basename is not None:
        entry["basename"] = basename
    all_views.append(entry)


class APIRouter(routers.DefaultRouter):
    def __init__(self):
        super().__init__()
        self.registered_api_views = set()
        self._register_all_views()

    def _register_view(self, view):
        if view["class"] in self.registered_api_views:
            return
        self.registered_api_views.add(view["class"])
        self.register(view["name"], view["class"], basename=view.get("basename"))

    def _register_all_views(self):
        for view in all_views:
            self._register_view(view)


register_view(ResourceViewSet, "resource", basename="resource")
register_view(DatePeriodViewSet, "date_period", basename="date_period")
register_view(RuleViewSet, "rule", basename="rule")
register_view(TimeSpanViewSet, "time_span", basename="time_span")
register_view(OrganizationViewSet, "organization", basename="organization")
register_view(OpeningHoursViewSet, "opening_hours", basename="opening_hours")
register_view(
    DatePeriodsAsTextForTprek,
    "date_periods_as_text_for_tprek",
    basename="date_periods_as_text_for_tprek",
)
register_view(AuthRequiredTestView, "auth_required_test", basename="auth_required_test")
