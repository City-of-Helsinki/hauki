import datetime
import re
from typing import Optional

from dateutil.parser import parse
from dateutil.relativedelta import MO, SU, relativedelta
from django.db.models import Q
from django.forms import Field
from django.utils import timezone
from django_filters import Filter, constants
from django_filters import rest_framework as filters

from .models import DatePeriod, Resource, Rule, TimeSpan
from .utils import get_resource_pk_filter


def parse_maybe_relative_date_string(
    date_string: str, end_date: bool = False
) -> Optional[datetime.date]:
    """
    Parses given string as python date.

    Parameters:
    input (str): String to parse
    end_date (bool): For relative shorthands, whether we should return the end date of
    the specified interval. The default behavior is to return the start date of weeks,
    months or years.

    We support shorthands for commonly requested start and end dates (e.g. -7d, -1w,
    +1y), e.g.
        * start date of this week is returned by +0w or -0w
        * end date of this week is returned by +0w or -0w, end_date=True
        * start date of last month is returned by -1m
        * start date of next month is returned by +1m
        * end date of last month is returned by -1m, end_date=True
        * start date of this year is returned by +0y or -0y
        * end date of this year is returned by +0y or -0y, end_date=True
    """
    if not date_string:
        return None

    today = timezone.now().date()

    # Special strings
    if date_string == "today":
        return today

    # Shorthands
    match = re.fullmatch(r"([-+]?)\s*(\d+)([dwmy])", date_string)

    if match:
        RELATIVEDELTA_PARAM_MAP = {
            "d": "days",
            "w": "weeks",
            "m": "months",
            "y": "years",
        }

        relativedelta_params = {
            RELATIVEDELTA_PARAM_MAP[match.group(3)]: int(
                match.group(1) + match.group(2)
            )
        }

        if match.group(3) == "w":
            relativedelta_params["weekday"] = MO(-1) if not end_date else SU

        elif match.group(3) == "m":
            relativedelta_params["day"] = 1 if not end_date else 31

        elif match.group(3) == "y":
            relativedelta_params["month"] = 1 if not end_date else 12
            relativedelta_params["day"] = 1 if not end_date else 31

        return today + relativedelta(**relativedelta_params)

    # Try to parse the exact date
    try:
        return parse(date_string, fuzzy=False).date()
    except ValueError:
        return None


class MaybeRelativeDateField(Field):
    def __init__(self, *args, **kwargs):
        self.end_date = False
        if "end_date" in kwargs:
            self.end_date = kwargs.pop("end_date")

        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return

        value = value.strip()

        return parse_maybe_relative_date_string(value, end_date=self.end_date)


class MaybeRelativeNullableDateFilter(Filter):
    field_class = MaybeRelativeDateField

    def filter(self, qs, value):
        if value in constants.EMPTY_VALUES:
            return qs
        if self.distinct:
            qs = qs.distinct()
        if self.lookup_expr in ("lte_or_null", "gte_or_null"):
            range_lookup = "%s__%s" % (
                self.field_name,
                self.lookup_expr.split("_or_")[0],
            )
            null_lookup = "%s__isnull" % self.field_name
            q = Q(**{range_lookup: value}) | Q(**{null_lookup: True})
            qs = self.get_method(qs)(q)
        else:
            lookup = "%s__%s" % (self.field_name, self.lookup_expr)
            qs = self.get_method(qs)(**{lookup: value})
        return qs


class DatePeriodFilter(filters.FilterSet):
    data_source = filters.CharFilter(field_name="origins__data_source")
    resource = filters.CharFilter(method="resource_filter")
    resource_data_source = filters.CharFilter(method="resource_data_source_filter")

    start_date = MaybeRelativeNullableDateFilter()
    end_date = MaybeRelativeNullableDateFilter()
    start_date_gte = MaybeRelativeNullableDateFilter(
        field_name="start_date", lookup_expr="gte"
    )
    start_date_lte = MaybeRelativeNullableDateFilter(
        field_name="start_date", lookup_expr="lte_or_null"
    )
    end_date_gte = MaybeRelativeNullableDateFilter(
        field_name="end_date", lookup_expr="gte_or_null", end_date=True
    )
    end_date_lte = MaybeRelativeNullableDateFilter(
        field_name="end_date", lookup_expr="lte", end_date=True
    )

    class Meta:
        model = DatePeriod
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        filters = map(get_resource_pk_filter, value.split(","))
        q_objects = [Q(**filter) for filter in filters]
        query_q = Q()
        for q in q_objects:
            query_q |= q
        try:
            resources = Resource.objects.filter(query_q)
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(resource__in=resources)

    def resource_data_source_filter(self, queryset, name, value):
        if name != "resource_data_source":
            return queryset

        queryset = queryset.filter(
            Q(resource__data_sources=value)
            | Q(resource__ancestry_data_source__contains=[value])
        )

        return queryset


class TimeSpanFilter(filters.FilterSet):
    resource = filters.CharFilter(method="resource_filter")

    class Meta:
        model = TimeSpan
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        filters = map(get_resource_pk_filter, value.split(","))
        q_objects = [Q(**filter) for filter in filters]
        query_q = Q()
        for q in q_objects:
            query_q |= q
        try:
            resources = Resource.objects.filter(query_q)
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(group__period__resource__in=resources)


class RuleFilter(TimeSpanFilter):
    class Meta:
        model = Rule
        fields = ["resource"]
