from rest_framework import routers, serializers, viewsets, filters
from django.forms import TextInput
import django_filters
from drf_extra_fields.fields import DateRangeField
from datetime import datetime, date, MINYEAR, MAXYEAR
from psycopg2.extras import DateRange

from .models import Target, TargetIdentifier, DailyHours, Opening, Period, Status, TargetType, Weekday

all_views = []


def register_view(klass, name, basename=None):
    entry = {'class': klass, 'name': name}
    if basename is not None:
        entry['basename'] = basename
    all_views.append(entry)


def parse_date(date: str) -> date:
    """
    Parses given string as python date.
    """
    if not date:
        return None
    if date == 'today':
        return datetime.now().date()
    return datetime.strptime(date, '%Y-%m-%d').date()


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
        end = parse_date(request.query_params.get('end', None))
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
