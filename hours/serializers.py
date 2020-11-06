from operator import itemgetter

from django_orghierarchy.models import Organization
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from modeltranslation import settings as mt_settings
from modeltranslation.translator import NotRegistered, translator
from modeltranslation.utils import get_language
from rest_framework import serializers

from users.serializers import UserSerializer

from .enums import State
from .models import (
    DataSource,
    DatePeriod,
    Resource,
    ResourceOrigin,
    Rule,
    TimeSpan,
    TimeSpanGroup,
)


class TranslationSerializerMixin:
    def to_representation(self, instance):
        result = super().to_representation(instance)

        try:
            translation_options = translator.get_options_for_model(instance.__class__)
        except NotRegistered:
            return result

        fields = self._readable_fields

        for field in fields:
            if field.field_name not in translation_options.fields.keys():
                continue

            new_value = {}
            for lang in mt_settings.AVAILABLE_LANGUAGES:
                key = f"{field.field_name}_{lang}"
                new_value[lang] = getattr(instance, key)

            result[field.field_name] = new_value

        return result

    def to_internal_value(self, data):
        try:
            translation_options = translator.get_options_for_model(self.Meta.model)
        except NotRegistered:
            return super().to_internal_value(data)

        current_language = get_language()

        for field_name in translation_options.fields.keys():
            if field_name not in data.keys():
                continue

            if not isinstance(data.get(field_name), dict):
                continue

            for lang in mt_settings.AVAILABLE_LANGUAGES:
                key = f"{field_name}_{lang}"
                data[key] = data.get(field_name, {}).get(lang, None)

            data[field_name] = data[f"{field_name}_{current_language}"]

        return super().to_internal_value(data)


class OrganizationSerializer(serializers.ModelSerializer):
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)
    classification = serializers.PrimaryKeyRelatedField(read_only=True)
    children = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="organization-detail"
    )

    class Meta:
        model = Organization
        fields = [
            "id",
            "data_source",
            "origin_id",
            "name",
            "classification",
            "parent",
            "children",
            "created_time",
            "last_modified_time",
        ]


class DataSourceSerializer(TranslationSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "name"]


class ResourceOriginSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer()

    class Meta:
        model = ResourceOrigin
        fields = ["data_source", "origin_id"]


class ResourceSerializer(
    TranslationSerializerMixin, EnumSupportSerializerMixin, serializers.ModelSerializer
):
    last_modified_by = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    origins = ResourceOriginSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "name",
            "description",
            "address",
            "resource_type",
            "children",
            "parents",
            "organization",
            "origins",
            "last_modified_by",
            "extra_data",
        ]

        read_only_fields = ["parents", "last_modified_by"]


class TimeSpanSerializer(
    TranslationSerializerMixin, EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = TimeSpan
        fields = [
            "id",
            "group",
            "name",
            "description",
            "start_time",
            "end_time",
            "full_day",
            "weekdays",
            "resource_state",
            "created",
            "modified",
        ]


class RuleSerializer(
    TranslationSerializerMixin, EnumSupportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Rule
        fields = [
            "id",
            "group",
            "name",
            "description",
            "context",
            "subject",
            "start",
            "frequency_ordinal",
            "frequency_modifier",
            "created",
            "modified",
        ]


class TimeSpanGroupSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    time_spans = TimeSpanSerializer(many=True)
    rules = RuleSerializer(many=True)

    class Meta:
        model = TimeSpanGroup
        fields = "__all__"


class DatePeriodSerializer(
    TranslationSerializerMixin, EnumSupportSerializerMixin, serializers.ModelSerializer
):
    time_span_groups = TimeSpanGroupSerializer(many=True)

    class Meta:
        model = DatePeriod
        fields = [
            "id",
            "resource",
            "name",
            "description",
            "start_date",
            "end_date",
            "resource_state",
            "override",
            "created",
            "modified",
            "time_span_groups",
        ]


class TimeElementSerializer(serializers.Serializer):
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    resource_state = EnumField(enum=State)
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
                        **time_element_serializer.data,
                    )
                )

        return sorted(result, key=itemgetter("date"))
