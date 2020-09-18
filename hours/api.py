from rest_framework import routers, serializers, viewsets, filters
from django.forms import TextInput
import django_filters
import re
from drf_extra_fields.fields import DateRangeField
from datetime import datetime, date, MINYEAR, MAXYEAR, timedelta
from calendar import monthrange
from psycopg2.extras import DateRange

from .models import Target, TargetIdentifier, DailyHours, Opening, Period, Status, TargetType, Weekday

all_views = []


def register_view(klass, name, basename=None):
    entry = {'class': klass, 'name': name}
    if basename is not None:
        entry['basename'] = basename
    all_views.append(entry)


def parse_date(date_string: str, end_date: bool = False) -> date:
    """
    Parses given string as python date.

    Parameters:
    input (str): String to parse
    end_date (bool): For relative shorthands, whether we should return the end date of the specified interval.
    The default behavior is to return the start date of weeks, months or years.

    We support shorthands for commonly requested start and end dates (e.g. -7d, -1w, +1y), e.g.
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
    today = datetime.now().date()

    # special strings
    if date_string == 'today':
        return today

    # shorthands
    timedelta_pattern = re.compile(r'([-+\s]?)([0-9]+)([dwmy])')
    match = timedelta_pattern.fullmatch(date_string)
    if match:
        sign = -1 if match.group(1) == '-' else 1
        multiplier = sign*int(match.group(2))
        if match.group(3) == 'd':
            return today + timedelta(days=multiplier)
        if match.group(3) == 'w':
            # return start or end of week
            if end_date:
                weekday_offset = 6 - today.weekday()
            else:
                weekday_offset = -today.weekday()
            return today + timedelta(days=7 * multiplier + weekday_offset)
        if match.group(3) == 'm':
            # check if the year changes
            if sign == 1:
                year_offset = (multiplier + today.month - 1) // 12
            else:
                year_offset = (multiplier + today.month - 12) // 12
            # the remainder is the change in months
            month_offset = multiplier - 12 * year_offset

            year_to_return = today.year + year_offset
            month_to_return = today.month + month_offset

            # return start or end of month
            day_to_return = monthrange(year_to_return, month_to_return)[1] if end_date else 1
            return date(year_to_return, month_to_return, day_to_return)
        if match.group(3) == 'y':
            year_to_return = today.year + multiplier

            # return start or end of year
            month_to_return = 12 if end_date else 1
            day_to_return = monthrange(year_to_return, month_to_return)[1] if end_date else 1
            return date(year_to_return, month_to_return, day_to_return)

    # standard iso dates
    return datetime.strptime(date_string, '%Y-%m-%d').date()


class APIRouter(routers.DefaultRouter):
    def __init__(self):
        super().__init__()
        self.registered_api_views = set()
        self._register_all_views()

    def _register_view(self, view):
        if view['class'] in self.registered_api_views:
            return
        self.registered_api_views.add(view['class'])
        self.register(view['name'], view['class'], basename=view.get("basename"))

    def _register_all_views(self):
        for view in all_views:
            self._register_view(view)


class IntegerChoiceField(serializers.ChoiceField):
    def __init__(self, choices, **kwargs):
        self.enum = choices
        super().__init__(choices, **kwargs)

    def to_representation(self, obj):
        return self.enum(obj).label


class IdentifierSerializer(serializers.HyperlinkedModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TargetIdentifier
        fields = ['data_source', 'origin_id']


class OpeningSerializer(serializers.HyperlinkedModelSerializer):
    status = IntegerChoiceField(choices=Status)
    weekday = IntegerChoiceField(choices=Weekday)

    class Meta:
        model = Opening
        fields = ['status', 'opens', 'closes', 'description', 'period', 'weekday',
                  'week', 'month', 'created_time', 'last_modified_time']


class DailyHoursSerializer(serializers.HyperlinkedModelSerializer):
    opening = OpeningSerializer()

    class Meta:
        model = DailyHours
        fields = ['date', 'target', 'opening']


# class DailyHoursRelatedField(serializers.RelatedField):
#     # Only display one week by default
#     # TODO: Currently no easy way of doing this in django, get_queryset doesn't exist :(
#     def get_queryset(self):
#         print('getting queryset')
#         today = datetime.date(datetime.now())
#         print(today)
#         return super().get_queryset().filter(date__range=(today, today))

#     def to_representation(self, value):
#         print('representing')
#         return DailyHoursSerializer(context=self.context).to_representation(value)


class TargetSerializer(serializers.HyperlinkedModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    target_type = IntegerChoiceField(choices=TargetType)
    identifiers = IdentifierSerializer(many=True)

    class Meta:
        model = Target
        fields = ['id', 'data_source', 'origin_id', 'organization', 'same_as', 'target_type',
                  'parent', 'second_parent', 'name', 'description',
                  'created_time', 'last_modified_time', 'publication_time',
                  'hours_updated', 'identifiers']


class PeriodSerializer(serializers.HyperlinkedModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)
    period = DateRangeField()
    openings = OpeningSerializer(many=True)
    status = IntegerChoiceField(choices=Status)

    class Meta:
        model = Period
        fields = ['id', 'data_source', 'origin_id', 'target',  'period', 'name', 'description',
                  'status', 'override', 'created_time', 'last_modified_time',
                  'publication_time', 'openings']


class TargetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Target.objects.all().prefetch_related('identifiers')
    serializer_class = TargetSerializer
    filterset_fields = ['data_source']


register_view(TargetViewSet, 'target')


class DateFilterBackend(filters.BaseFilterBackend):
    """
    Filters periods and daily hours based on date overlap.
    """
    def filter_queryset(self, request, queryset, view):
        start = parse_date(request.query_params.get('start', None))
        end = parse_date(request.query_params.get('end', None), end_date=True)
        if not start:
            start = date(MINYEAR, 1, 1)
        if not end:
            end = date(MAXYEAR, 12, 31)
        query_period = DateRange(start, end, bounds='[]')
        if hasattr(queryset.model, 'period'):
            return queryset.filter(period__overlap=query_period)
        if hasattr(queryset.model, 'date'):
            return queryset.filter(date__contained_by=query_period)
        return queryset


class PeriodFilterSet(django_filters.FilterSet):
    target = django_filters.ModelChoiceFilter(queryset=Target.objects.all(),
                                              widget=TextInput())

    class Meta:
        model = Period
        fields = ['target']


class PeriodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Period.objects.all().prefetch_related('openings')
    serializer_class = PeriodSerializer
    ordering = ['target']
    filterset_class = PeriodFilterSet
    filter_backends = [filters.OrderingFilter,
                       django_filters.rest_framework.DjangoFilterBackend,
                       DateFilterBackend]


register_view(PeriodViewSet, 'period')


class DailyHoursFilterSet(django_filters.FilterSet):
    target = django_filters.ModelChoiceFilter(queryset=Target.objects.all(),
                                              widget=TextInput())

    class Meta:
        model = DailyHours
        fields = ['target']


class DailyHoursViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyHours.objects.all().select_related('opening')
    serializer_class = DailyHoursSerializer
    ordering = ['date', 'target']
    filterset_class = DailyHoursFilterSet
    filter_backends = [filters.OrderingFilter,
                       django_filters.rest_framework.DjangoFilterBackend,
                       DateFilterBackend]


register_view(DailyHoursViewSet, 'daily_hours')
