from rest_framework import routers, serializers, viewsets, filters

from .models import Target, DailyHours, Opening, Period

all_views = []


def register_view(klass, name, base_name=None):
    entry = {'class': klass, 'name': name}
    if base_name is not None:
        entry['base_name'] = base_name
    all_views.append(entry)


class APIRouter(routers.DefaultRouter):
    def __init__(self):
        super().__init__()
        self.registered_api_views = set()
        self._register_all_views()

    def _register_view(self, view):
        if view['class'] in self.registered_api_views:
            return
        self.registered_api_views.add(view['class'])
        self.register(view['name'], view['class'], base_name=view.get("base_name"))

    def _register_all_views(self):
        for view in all_views:
            self._register_view(view)


class TargetSerializer(serializers.HyperlinkedModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Target
        fields = ['id', 'data_source', 'origin_id', 'same_as', 'target_type',
              'parent', 'second_parent', 'name', 'description',
              'created_time', 'last_modified_time', 'publication_time',
              'hours_updated']


class TargetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    filter_backends = [filters.OrderingFilter]


register_view(TargetViewSet, 'target')


class OpeningSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Opening
        fields = ['status', 'opens', 'closes', 'description', 'period', 'weekday',
            'week', 'month', 'created_time', 'last_modified_time']


class PeriodSerializer(serializers.HyperlinkedModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)
    openings = OpeningSerializer(many=True)

    class Meta:
        model = Period
        fields = ['id', 'data_source', 'origin_id', 'target', 'name', 'description',
            'status', 'override', 'period', 'created_time', 'last_modified_time',
            'publication_time', 'openings']


class PeriodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['target']


register_view(PeriodViewSet, 'period')


class DailyHoursSerializer(serializers.HyperlinkedModelSerializer):
    opening = OpeningSerializer()

    class Meta:
        model = DailyHours
        fields = ['target', 'date', 'opening']


class DailyHoursViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyHours.objects.all()
    serializer_class = DailyHoursSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['date', 'target']


register_view(DailyHoursViewSet, 'daily_hours')