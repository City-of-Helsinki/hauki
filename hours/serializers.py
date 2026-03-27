from collections import OrderedDict

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from drf_spectacular.utils import extend_schema_field
from drf_writable_nested import UniqueFieldsMixin, WritableNestedModelSerializer
from modeltranslation import settings as mt_settings
from modeltranslation.translator import NotRegistered, translator
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SkipField, get_error_detail
from timezone_field.rest_framework import TimeZoneSerializerField

from users.serializers import UserSerializer

from .authentication import HaukiSignedAuthData
from .enums import State
from .exceptions import Conflict
from .fields import TimezoneRetainingDateTimeField
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
from .permissions import filter_queryset_by_permission


@extend_schema_field(
    {
        "type": "object",
        "properties": {
            lang: {"type": "string", "nullable": True}
            for lang in mt_settings.AVAILABLE_LANGUAGES
        },
    }
)
class TranslatedField(serializers.CharField):
    """A CharField that is rendered as a multilingual object in the OpenAPI schema.

    The actual transformation of the value is handled by TranslationSerializerMixin;
    this class only exists to carry the correct drf-spectacular schema annotation.
    """


class TranslationSerializerMixin:
    def get_fields(self):
        fields = super().get_fields()
        try:
            translation_options = translator.get_options_for_model(self.Meta.model)
        except (NotRegistered, AttributeError):
            return fields

        for field_name in translation_options.all_fields.keys():
            if field_name not in fields:
                continue
            original = fields[field_name]
            if isinstance(original, serializers.CharField) and not isinstance(
                original, TranslatedField
            ):
                translated = TranslatedField(
                    required=original.required,
                    allow_null=original.allow_null,
                    allow_blank=getattr(original, "allow_blank", True),
                    read_only=original.read_only,
                    write_only=original.write_only,
                    default=original.default,
                    source=original.source,
                    label=original.label,
                    help_text=original.help_text,
                    style=original.style,
                    max_length=getattr(original, "max_length", None),
                    min_length=getattr(original, "min_length", None),
                )
                fields[field_name] = translated
        return fields

    def to_representation(self, instance):
        result = super().to_representation(instance)

        try:
            translation_options = translator.get_options_for_model(instance.__class__)
        except NotRegistered:
            return result

        fields = self._readable_fields

        for field in fields:
            if field.field_name not in translation_options.all_fields.keys():
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

        translated_values = {}

        # Add the possibly existing already internalized values to the
        # translated_values variable. Otherwise we would lose the values
        # if to_internal_value is called twice (as is the case with nested serializers).
        for field_name in translation_options.all_fields.keys():
            for lang in mt_settings.AVAILABLE_LANGUAGES:
                translation_field_name = f"{field_name}_{lang}"
                if translation_field_name in data:
                    translated_values[translation_field_name] = data.get(
                        translation_field_name
                    )

        errors = OrderedDict()
        for field_name in translation_options.all_fields.keys():
            if field_name not in data.keys():
                continue

            if not isinstance(data.get(field_name), dict):
                continue

            field_values = data.get(field_name, {})
            validate_method = getattr(self, "validate_" + field_name, None)
            field = self.fields[field_name]
            for lang in mt_settings.AVAILABLE_LANGUAGES:
                try:
                    primitive_value = field_values[lang]
                except KeyError:
                    # allow omitting some languages to patch
                    continue
                try:
                    validated_value = field.run_validation(primitive_value)
                    if validate_method is not None:
                        validated_value = validate_method(validated_value)
                except ValidationError as exc:
                    errors[field_name] = exc.detail
                except DjangoValidationError as exc:
                    errors[field_name] = get_error_detail(exc)
                except SkipField:
                    pass
                else:
                    # set_value(translated_values, field.source_attrs, validated_value)
                    translated_values[f"{field_name}_{lang}"] = validated_value
                if lang not in field_values:
                    continue

                # Set the fields also in the initial_data, because the serializer
                # save uses the initial data and not the validated_data when saving
                data[f"{field_name}_{lang}"] = field_values[lang]

            del data[field_name]

        if errors:
            raise ValidationError(errors)
        other_values = super().to_internal_value(data)
        other_values.update(**translated_values)

        return other_values


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


class DataSourceSerializer(
    UniqueFieldsMixin, TranslationSerializerMixin, serializers.ModelSerializer
):
    name = serializers.CharField(read_only=True)

    def validate(self, attrs):
        """Validate that the data_source exists and corresponds to the user
        data source"""
        result = super().validate(attrs)

        try:
            self.instance = self.Meta.model.objects.get(id=result["id"])
        except self.Meta.model.DoesNotExist:
            raise ValidationError(
                detail=_(f"Data source {result['id']} does not exist.")
            )

        user = self.context["request"].user
        if self.instance not in [origin.data_source for origin in user.origins.all()]:
            raise ValidationError(
                detail=_("Cannot add origin_ids for a different data source.")
            )

        # Data from some data sources is read-only
        if not (self.instance.user_editable_resources):
            raise ValidationError(
                detail=_(f"All data from data source {self.instance.id} is read-only.")
            )

        return result

    class Meta:
        model = DataSource
        fields = ["id", "name"]


class ResourceOriginSerializer(WritableNestedModelSerializer):
    data_source = DataSourceSerializer()

    class Meta:
        model = ResourceOrigin
        fields = ["data_source", "origin_id"]


class WritableNestedOriginsMixin:
    """Mixin providing a reusable helper for saving reverse-relation instances."""

    def _save_reverse_relation_field(
        self,
        instance,
        related_field,
        field,
        field_name: str,
        field_source: str,
        instances,
        related_data,
    ) -> None:
        """Save *instances* paired with *related_data* under *instance*.

        Builds ``save_kwargs``, iterates the pairs, collects validation errors
        and raises ``ValidationError`` if any are found.  Wires up many-to-many
        relations via the manager when required.
        """
        save_kwargs = self._get_save_kwargs(field_name)
        if isinstance(related_field, GenericRelation):
            save_kwargs.update(
                self._get_generic_lookup(instance, related_field),
            )
        elif not related_field.many_to_many:
            save_kwargs[related_field.name] = instance

        new_related_instances = []
        errors = []
        for obj, data in zip(instances, related_data):
            serializer = self._get_serializer_for_field(
                field,
                instance=obj,
                data=data,
            )
            try:
                serializer.is_valid(raise_exception=True)
                related_instance = serializer.save(**save_kwargs)
                data["pk"] = related_instance.pk
                new_related_instances.append(related_instance)
                errors.append({})
            except ValidationError as exc:
                errors.append(exc.detail)

        if any(errors):
            if related_field.one_to_one:
                raise ValidationError({field_name: errors[0]})
            else:
                raise ValidationError({field_name: errors})

        if related_field.many_to_many:
            # Add m2m instances to through model via add
            m2m_manager = getattr(instance, field_source)
            m2m_manager.add(*new_related_instances)


class ResourceSerializer(
    WritableNestedOriginsMixin,
    TranslationSerializerMixin,
    WritableNestedModelSerializer,
):
    last_modified_by = UserSerializer(read_only=True)
    origins = ResourceOriginSerializer(many=True, required=False, allow_null=True)
    timezone = TimeZoneSerializerField(required=False)

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
            "created",
            "modified",
            "extra_data",
            "is_public",
            "timezone",
            "date_periods_hash",
            "date_periods_as_text",
        ]

        read_only_fields = [
            "last_modified_by",
            "date_periods_hash",
            "date_periods_as_text",
        ]
        extra_kwargs = {"parents": {"required": False}, "origins": {"required": False}}

    def _prefetch_related_instances(self, field, related_data):
        """
        Override WritableNestedModelSerializer behavior (tries to create new related
        instances) in the case of resource origins. This allows us to re-use origins
        from existing objects, in case origins are moved to a new resource.

        Returns an iterable of same length as related_data, containing
        corresponding instances or None if instance was not found.
        """
        related_origins = []
        for datum in related_data:
            try:
                origin = ResourceOrigin.objects.get(
                    data_source=datum["data_source"]["id"], origin_id=datum["origin_id"]
                )
            except ResourceOrigin.DoesNotExist:
                origin = None
            related_origins.append(origin)
        return related_origins

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        """
        Override WritableNestedModelSerializer behavior (tries to create new related
        instances) in the case of resource origins. This allows us to re-use origins
        from existing objects, in case origins are moved to a new resource.

        Currently, resources have no other reverse relations, but this method is here
        for future-proofing and WritableNestedModelSerializer compatibility.
        """
        # Update or create reverse relations:
        # many-to-one, many-to-many, reversed one-to-one
        for field_name, (
            related_field,
            field,
            field_source,
        ) in reverse_relations.items():
            # Skip processing for empty data or not-specified field.
            # The field can be defined in validated_data but isn't defined
            # in initial_data (for example, if multipart form data used)
            related_data = self.get_initial().get(field_name, None)
            if related_data is None:
                continue

            instances = self._prefetch_related_instances(field, related_data)

            self._save_reverse_relation_field(
                instance,
                related_field,
                field,
                field_name,
                field_source,
                instances,
                related_data,
            )

    def _check_duplicate_origins(self, origins):
        """Single-query duplicate-origin guard; raises Conflict on the first match.

        Fetches all potentially conflicting ResourceOrigins in one query, then
        iterates the request-supplied origins in order so the conflict is always
        raised for the first duplicate rather than an arbitrary one.
        """
        duplicate_filter = Q()
        for origin in origins:
            duplicate_filter |= Q(
                data_source_id=origin["data_source"]["id"],
                origin_id=origin["origin_id"],
            )
        existing_origins_by_pair = {
            (eo.data_source_id, eo.origin_id): eo
            for eo in ResourceOrigin.objects.select_related("resource").filter(
                duplicate_filter
            )
        }

        request = self.context.get("request")
        for origin in origins:
            ds_id = origin["data_source"]["id"]
            origin_id = origin["origin_id"]
            existing_origin = existing_origins_by_pair.get((ds_id, origin_id))
            if existing_origin is None:
                continue

            # Only include the full resource payload when the requesting user
            # is actually allowed to read that resource.  Without this check
            # the conflict path would leak data from non-public resources in
            # organizations the caller cannot access.
            existing_resource = existing_origin.resource
            conflict_detail = {
                "message": _(
                    "Resource with origin %(ds_id)s:%(origin_id)s already exists."
                )
                % {"ds_id": ds_id, "origin_id": origin_id},
            }
            if (
                request is not None
                and filter_queryset_by_permission(
                    request.user,
                    Resource.objects.filter(pk=existing_resource.pk),
                    auth=request.auth,
                ).exists()
            ):
                conflict_detail["resource"] = ResourceSerializer(
                    existing_resource, context=self.context
                ).data
            raise Conflict(detail=conflict_detail)

    def _validate_parent_permissions(self, user, auth, parents):
        """Validate that the user may create/edit sub-resources under *parents*.

        Raises ``ValidationError`` when the caller lacks the required rights.
        Returns ``True`` when the HaukiSignedAuth authorized-resource path
        grants unconditional access (signals ``validate`` to return early),
        ``False`` otherwise.
        """
        if isinstance(auth, HaukiSignedAuthData):
            # A special case for users signed in using the HaukiSignedAuthentication
            authorized_resource = auth.resource
            if authorized_resource:
                resource_ancestors = set(parents)
                for parent in parents:
                    resource_ancestors.update(parent.get_ancestors())
                #             authorized_resource
                #                      |
                #                      |
                #                      |
                #    parent A       parent B
                # not authorized   authorized
                #        |             |
                #        +------+------+
                #               |
                #           resource
                authorized_ancestors = authorized_resource.get_ancestors()
                authorized_descendants = authorized_resource.get_descendants()
                if not resource_ancestors.difference(
                    authorized_ancestors
                    | {authorized_resource}
                    | authorized_descendants
                ):
                    # Parents allowed only if no extra parents found
                    # in the ancestor chain
                    return True
            if not auth.has_organization_rights:
                raise ValidationError(
                    detail=_(
                        "Cannot create or edit sub resources of a resource "
                        "in an organisation the user is not part of "
                    )
                )

        users_organizations = user.get_all_organizations()
        if not all(parent.organization in users_organizations for parent in parents):
            raise ValidationError(
                detail=_(
                    "Cannot create or edit sub resources of a resource "
                    "in an organisation the user is not part of "
                )
            )
        return False

    def validate(self, attrs):
        """Validate that the user is a member or admin of all of the
        immediate parent resources organizations"""
        result = super().validate(attrs)

        # When creating a new resource, reject origins that already belong to
        # another resource by returning HTTP 409 Conflict.
        if self.instance is None:
            origins = result.get("origins") or []
            if origins:
                self._check_duplicate_origins(origins)

        if not self.context.get("request"):
            return result

        user = self.context["request"].user
        auth = self.context["request"].auth
        parents = result.get("parents")

        if not user.is_superuser and parents:
            if self._validate_parent_permissions(user, auth, parents):
                return result

        return result


class ResourceSimpleSerializer(TranslationSerializerMixin, serializers.ModelSerializer):
    timezone = TimeZoneSerializerField()
    origins = ResourceOriginSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "name",
            "timezone",
            "origins",
        ]


class TimeSpanCreateSerializer(TranslationSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = TimeSpan
        fields = [
            "id",
            "group",
            "name",
            "description",
            "start_time",
            "end_time",
            "end_time_on_next_day",
            "full_day",
            "weekdays",
            "resource_state",
            "created",
            "modified",
        ]

    def validate(self, attrs):
        if "end_time_on_next_day" in attrs:
            return attrs

        if attrs.get("start_time") and attrs.get("end_time"):
            # Populate end_time_on_next_day field if it's not set
            attrs["end_time_on_next_day"] = attrs["end_time"] <= attrs["start_time"]

        return attrs


class TimeSpanSerializer(TimeSpanCreateSerializer):
    # Group should not be required when saving a nested object
    group = serializers.PrimaryKeyRelatedField(
        required=False, queryset=TimeSpanGroup.objects.all()
    )


class RuleCreateSerializer(TranslationSerializerMixin, serializers.ModelSerializer):
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


class TimeSpanGroupSerializer(WritableNestedModelSerializer):
    period = serializers.PrimaryKeyRelatedField(
        required=False, queryset=DatePeriod.objects.all()
    )
    time_spans = TimeSpanSerializer(many=True, required=False, allow_null=True)
    rules = RuleSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = TimeSpanGroup
        fields = "__all__"


class PeriodOriginSerializer(WritableNestedModelSerializer):
    data_source = DataSourceSerializer()

    class Meta:
        model = PeriodOrigin
        fields = ["data_source", "origin_id"]


class DatePeriodSerializer(
    WritableNestedOriginsMixin,
    TranslationSerializerMixin,
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
            "order",
            "origins",
            "created",
            "modified",
            "time_span_groups",
        ]

    def _prefetch_related_instances(self, field, related_data):
        """
        Override WritableNestedModelSerializer behavior for period origins.

        Re-uses existing PeriodOrigin instances identified by
        (data_source_id, origin_id, period), enabling origins to be updated
        in place without unique-constraint violations.

        On create (``self.instance is None``) always returns ``None`` entries
        so new rows are created.  On update the lookup is scoped to the period
        being modified, so origins on other periods are never matched.

        For all other related fields the parent behavior is preserved.

        Note: drf-writable-nested passes the *child* serializer here (not the
        ListSerializer), so we check ``isinstance(field, PeriodOriginSerializer)``.
        """
        if not isinstance(field, PeriodOriginSerializer):
            return super()._prefetch_related_instances(field, related_data)

        # On create there are no existing rows to look up.
        if self.instance is None or not related_data:
            return [None] * len(related_data)

        # Fetch all candidate rows in a single query instead of one
        # PeriodOrigin.objects.get() per entry (N+1), then map by
        # (data_source_id, origin_id) for O(1) lookup while preserving order.
        candidate_filter = Q()
        for datum in related_data:
            candidate_filter |= Q(
                data_source_id=datum["data_source"]["id"],
                origin_id=datum["origin_id"],
            )
        existing_by_pair = {
            (eo.data_source_id, eo.origin_id): eo
            for eo in PeriodOrigin.objects.filter(
                candidate_filter, period=self.instance
            )
        }

        return [
            existing_by_pair.get((datum["data_source"]["id"], datum["origin_id"]))
            for datum in related_data
        ]

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        origins_item = reverse_relations.pop("origins", None)

        # Parent handles time_span_groups and any other reverse relations normally
        # (including deletion of removed time_span_groups on full PUT/PATCH).
        super().update_or_create_reverse_relations(instance, reverse_relations)

        if origins_item is None:
            return

        related_field, field, field_source = origins_item
        related_data = self.get_initial().get("origins", None)
        if related_data is None:
            return

        instances = self._prefetch_related_instances(field, related_data)

        self._save_reverse_relation_field(
            instance,
            related_field,
            field,
            "origins",
            field_source,
            instances,
            related_data,
        )

    def _check_duplicate_origins(self, origins, resource=None):
        """Single-query duplicate-origin guard; raises Conflict on the first match.

        Fetches all potentially conflicting PeriodOrigins in one query, then
        iterates the request-supplied origins in order so the conflict is always
        raised for the first duplicate rather than an arbitrary one.

        Origins that already exist on DatePeriods of *the same resource* are
        explicitly allowed — only cross-resource duplicates are rejected.
        """
        duplicate_filter = Q()
        for origin in origins:
            duplicate_filter |= Q(
                data_source_id=origin["data_source"]["id"],
                origin_id=origin["origin_id"],
            )
        existing_origins_qs = PeriodOrigin.objects.select_related("period").filter(
            duplicate_filter
        )
        # Same-resource DatePeriods may share origins — exclude them from conflict
        # detection so only cross-resource duplicates trigger a 409.
        if resource is not None:
            existing_origins_qs = existing_origins_qs.exclude(period__resource=resource)
        existing_origins_by_pair = {
            (eo.data_source_id, eo.origin_id): eo for eo in existing_origins_qs
        }

        request = self.context.get("request")
        for origin in origins:
            ds_id = origin["data_source"]["id"]
            origin_id = origin["origin_id"]
            existing_origin = existing_origins_by_pair.get((ds_id, origin_id))
            if existing_origin is None:
                continue

            # Only include the full date_period payload when the requesting user
            # is actually allowed to read that period. Without this check the
            # conflict path would leak data from non-public periods in
            # organizations the caller cannot access.
            existing_period = existing_origin.period
            conflict_detail = {
                "message": _(
                    "DatePeriod with origin %(ds_id)s:%(origin_id)s already exists."
                )
                % {"ds_id": ds_id, "origin_id": origin_id},
            }
            if (
                request is not None
                and filter_queryset_by_permission(
                    request.user,
                    DatePeriod.objects.filter(pk=existing_period.pk),
                    auth=request.auth,
                ).exists()
            ):
                conflict_detail["date_period"] = DatePeriodSerializer(
                    existing_period, context=self.context
                ).data
            raise Conflict(detail=conflict_detail)

    def validate(self, attrs):
        result = super().validate(attrs)

        # Reject origins that already belong to a *different* resource's
        # date period (HTTP 409 Conflict).  This must run on both create
        # *and* update so that a PATCH cannot introduce a cross-resource
        # duplicate.  Origins shared across multiple periods of the same
        # resource are still allowed.
        origins = result.get("origins") or []
        if origins:
            # On PATCH, `resource` may not be in attrs; fall back to the
            # existing instance's resource.
            resource = result.get("resource") or (
                self.instance.resource if self.instance is not None else None
            )
            self._check_duplicate_origins(origins, resource=resource)

        return result


class TimeElementSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    end_time_on_next_day = serializers.BooleanField()
    resource_state = serializers.ChoiceField(choices=State.choices)
    full_day = serializers.BooleanField()
    periods = serializers.SerializerMethodField()

    def get_periods(self, obj):
        # Return only period ids for now
        # TODO: what else we would like to see in the API about the periods
        return [period.id for period in obj.periods]


class DailyOpeningHoursSerializer(serializers.Serializer):
    date = serializers.DateField()
    times = TimeElementSerializer(many=True)


class ResourceDailyOpeningHoursSerializer(serializers.Serializer):
    origin_id = serializers.CharField(required=False)
    resource = ResourceSimpleSerializer()
    opening_hours = DailyOpeningHoursSerializer(many=True)


class IsOpenNowSerializer(serializers.Serializer):
    is_open = serializers.BooleanField()
    resource_timezone = TimeZoneSerializerField(required=False)
    resource_time_now = serializers.DateTimeField()
    matching_opening_hours = TimeElementSerializer(many=True)

    other_timezone = TimeZoneSerializerField(required=False)
    other_timezone_time_now = TimezoneRetainingDateTimeField(required=False)
    matching_opening_hours_in_other_tz = TimeElementSerializer(
        many=True, required=False
    )

    resource = ResourceSerializer()
