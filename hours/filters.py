import datetime
import re
from typing import Optional

from dateutil.parser import parse
from dateutil.relativedelta import MO, SU, relativedelta
from django.forms import Field
from django.utils import timezone
from django_filters import Filter
from django_filters import rest_framework as filters

from .models import DatePeriod, Resource, TimeSpan
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


class MaybeRelativeDateFilter(Filter):
    field_class = MaybeRelativeDateField


class DatePeriodFilter(filters.FilterSet):
    resource = filters.CharFilter(method="resource_filter")
    start_date = MaybeRelativeDateFilter()
    end_date = MaybeRelativeDateFilter()
    start_date_gte = MaybeRelativeDateFilter(field_name="start_date", lookup_expr="gte")
    start_date_lte = MaybeRelativeDateFilter(field_name="start_date", lookup_expr="lte")
    end_date_gte = MaybeRelativeDateFilter(
        field_name="end_date", lookup_expr="gte", end_date=True
    )
    end_date_lte = MaybeRelativeDateFilter(
        field_name="end_date", lookup_expr="lte", end_date=True
    )

    class Meta:
        model = DatePeriod
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        try:
            resource = Resource.objects.get(**get_resource_pk_filter(value))
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(resource=resource)


class TimeSpanFilter(filters.FilterSet):
    resource = filters.CharFilter(method="resource_filter")

    class Meta:
        model = TimeSpan
        fields = ["resource"]

    def resource_filter(self, queryset, name, value):
        if name != "resource":
            return queryset

        try:
            resource = Resource.objects.get(**get_resource_pk_filter(value))
        except (ValueError, Resource.DoesNotExist):
            return queryset

        return queryset.filter(group__period__resource=resource)
