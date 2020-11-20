from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from drf_writable_nested import WritableNestedModelSerializer
from enumfields.drf import EnumField, EnumSupportSerializerMixin
from modeltranslation import settings as mt_settings
from modeltranslation.translator import NotRegistered, translator
from modeltranslation.utils import get_language
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.serializers import UserSerializer

from .enums import State
from .models import (
    DataSource,
    DatePeriod,
    PeriodOrigin,
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

        read_only_fields = ["last_modified_by"]
        extra_kwargs = {"parents": {"required": False}}

    def validate(self, attrs):
        """Validate that the user is a member or admin of at least one of the
        immediate parent resources organizations"""
        result = super().validate(attrs)

        if not self.context.get("request"):
            return result

        user = self.context["request"].user

        if not user.is_superuser and result.get("parents"):
            users_organizations = user.get_all_organizations()
            if not any(
                [
                    parent.organization in users_organizations
                    for parent in result.get("parents")
                ]
            ):
                raise ValidationError(
                    detail=_(
                        "Cannot create or edit sub resources of a resource "
                        "in an organisation the user is not part of "
                    )
                )

        return result


class TimeSpanCreateSerializer(
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


class TimeSpanSerializer(TimeSpanCreateSerializer):
    # Group should not be required when saving a nested object
    group = serializers.PrimaryKeyRelatedField(
        required=False, queryset=TimeSpanGroup.objects.all()
    )


class RuleCreateSerializer(
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


class RuleSerializer(RuleCreateSerializer):
    # Group should not be required when saving a nested object
    group = serializers.PrimaryKeyRelatedField(
        required=False, queryset=TimeSpanGroup.objects.all()
    )


class TimeSpanGroupSerializer(
    EnumSupportSerializerMixin, WritableNestedModelSerializer
):
    period = serializers.PrimaryKeyRelatedField(
        required=False, queryset=DatePeriod.objects.all()
    )
    time_spans = TimeSpanSerializer(many=True, required=False, allow_null=True)
    rules = RuleSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = TimeSpanGroup
        fields = "__all__"


class PeriodOriginSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer()

    class Meta:
        model = PeriodOrigin
        fields = ["data_source", "origin_id"]


class DatePeriodSerializer(
    TranslationSerializerMixin,
    EnumSupportSerializerMixin,
    WritableNestedModelSerializer,
):
    time_span_groups = TimeSpanGroupSerializer(
        many=True, required=False, allow_null=True
    )
    origins = PeriodOriginSerializer(many=True, required=False, allow_null=True)

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
            "origins",
            "created",
            "modified",
            "time_span_groups",
        ]


class TimeElementSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    resource_state = EnumField(enum=State)
    full_day = serializers.BooleanField()
    periods = serializers.SerializerMethodField()

    def get_periods(self, obj):
        # Return only period ids for now
        # TODO: what else we would like to see in the API about the periods
        return [period.id for period in obj.periods]


class DailyOpeningHoursSerializer(serializers.Serializer):
    date = serializers.DateField()
    times = TimeElementSerializer(many=True)
