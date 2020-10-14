from operator import itemgetter

from django_orghierarchy.models import Organization
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from rest_framework import serializers

from users.serializers import UserSerializer

from .enums import PeriodType
from .models import DataSource, DatePeriod, OpeningHours, Resource, ResourceOrigin, Rule


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "name"]


class ResourceOriginSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer()

    class Meta:
        model = ResourceOrigin
        fields = ["data_source", "origin_id"]


class ResourceSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    last_modified_by = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    resourceorigin_set = ResourceOriginSerializer(
        many=True, required=False, allow_null=True
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            # TODO: Add fields for all of the languages automatically
            "name",
            "name_fi",
            "name_sv",
            "name_en",
            "description",
            "description_fi",
            "description_sv",
            "description_en",
            "address",
            "address_fi",
            "address_sv",
            "address_en",
            "resource_type",
            "parent",
            "organization",
            "resourceorigin_set",
            "last_modified_by",
            "extra_data",
        ]


class OpeningHoursSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = OpeningHours
        fields = "__all__"


class RuleSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = "__all__"


class DatePeriodSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    opening_hours = OpeningHoursSerializer(many=True)
    rules = RuleSerializer(many=True)

    class Meta:
        model = DatePeriod
        fields = "__all__"


class TimeElementSerializer(serializers.Serializer):
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    period_type = EnumField(enum=PeriodType)
    override = serializers.BooleanField()
    full_day = serializers.BooleanField()


class DailyOpeningHoursSerializer(serializers.BaseSerializer):
    def to_representation(self, instance: dict):
        result = []
        for date, time_elements in instance.items():
            for time_element in time_elements:
                time_element_serializer = TimeElementSerializer(time_element)
                result.append(
                    dict(
                        **{
                            "date": date.isoformat(),
                        },
                        **time_element_serializer.data
                    )
                )

        return sorted(result, key=itemgetter("date"))
