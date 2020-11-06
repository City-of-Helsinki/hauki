import logging
import os
import re
from collections.abc import Sized

import requests
from django import db
from django.db.models import Model
from model_utils.models import SoftDeletableModel
from modeltranslation.translator import translator

from hours.models import (
    DataSource,
    DatePeriod,
    Resource,
    ResourceOrigin,
    Rule,
    TimeSpan,
    TimeSpanGroup,
)


class Importer(object):
    def __init__(self, options):
        self.logger = logging.getLogger("%s_importer" % self.name)
        self.options = options
        self.setup()
        resource_origins = ResourceOrigin.objects.select_related("resource").filter(
            data_source=self.data_source
        )
        if self.options.get("single", None):
            resource_origins = resource_origins.filter(origin_id=self.options["single"])
        self.resource_cache = {
            origin.origin_id: origin.resource for origin in resource_origins
        }

    def get_url(self, resource_name: str, res_id: str = None) -> str:
        url = "%s%s/" % (self.URL_BASE, resource_name)
        if res_id is not None:
            url = "%s%s/" % (url, res_id)
        return url

    def api_get(
        self, resource_name: str, res_id: str = None, params: dict = None
    ) -> dict:
        url = self.get_url(resource_name, res_id)
        self.logger.info("Fetching URL %s with params %s " % (url, params))
        resp = requests.get(url, params)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def mark_deleted(obj: SoftDeletableModel) -> bool:
        return obj.delete()

    @staticmethod
    def check_deleted(obj: SoftDeletableModel) -> bool:
        return obj.is_removed

    @staticmethod
    def clean_text(text: str, strip_newlines: bool = False) -> str:
        # remove non-breaking spaces and separators
        text = text.replace("\xa0", " ").replace("\x1f", "")
        # remove nil bytes
        text = text.replace(u"\u0000", " ")
        if strip_newlines:
            text = text.replace("\r", "").replace("\n", " ")
        # remove consecutive whitespaces
        return re.sub(r"\s\s+", " ", text, re.U).strip()

    def _set_field(self, obj: object, field_name: str, val: object):
        """
        Sets the field_name field of obj to val, if changed.
        """
        if not hasattr(obj, field_name):
            self.logger.debug("'%s' not there!" % field_name)
            self.logger.debug(vars(obj))

        obj_val = getattr(obj, field_name, None)
        if obj_val == val:
            return

        field = obj._meta.get_field(field_name)
        if getattr(field, "max_length", None) and isinstance(val, Sized):
            if len(val) > field.max_length:
                raise Exception(
                    "field '%s' too long (max. %d): %s" % field_name,
                    field.max_length,
                    val,
                )

        setattr(obj, field_name, val)
        obj._changed = True
        if not hasattr(obj, "_changed_fields"):
            obj._changed_fields = []
        obj._changed_fields.append(field_name)

    def _update_fields(self, obj: object, info: dict, skip_fields: list = None):
        """
        Updates the fields in obj according to info.
        """
        if not skip_fields:
            skip_fields = []
        obj_fields = list(obj._meta.fields)
        trans_fields = translator.get_options_for_model(type(obj)).fields
        for field_name, lang_fields in trans_fields.items():
            lang_fields = list(lang_fields)
            for lf in lang_fields:
                lang = lf.language
                # Do not process this field later
                skip_fields.append(lf.name)

                if field_name not in info:
                    continue

                data = info[field_name]
                if data is not None and lang in data:
                    val = data[lang]
                else:
                    val = None
                self._set_field(obj, lf.name, val)

            # Remove original translated field
            skip_fields.append(field_name)

        for d in skip_fields:
            for f in obj_fields:
                if f.name == d:
                    obj_fields.remove(f)
                    break

        for field in obj_fields:
            field_name = field.name
            if field_name not in info:
                continue
            self._set_field(obj, field_name, info[field_name])

    def _update_or_create_object(self, klass: type, data: dict) -> Model:
        """
        Takes the class and serialized data, creates and/or updates the Model
        object and returns it unsaved for class-specific processing and saving.
        """
        # look for existing origin corresponding to the object
        cache = getattr(self, "%s_cache" % klass.__name__.lower())

        # if identical objects are merged, an object may have several
        # origin ids. all origin ids should return the same object.
        origin_ids = [
            str(origin["origin_id"])
            for origin in data["origins"]
            if origin["data_source_id"] == self.data_source.id
        ]
        obj = cache.get(origin_ids[0], None)
        if obj:
            obj._created = False
        else:
            obj = klass()
            obj._created = True
            # save the new object in the cache so related objects will find it
            setattr(
                self,
                "%s_cache" % klass.__name__.lower(),
                {**cache, **{origin_id: obj for origin_id in origin_ids}},
            )
        obj._changed = False
        obj._changed_fields = []

        self._update_fields(obj, data)
        self._set_field(obj, "is_removed", False)
        self._set_field(obj, "is_public", True)
        return obj

    @db.transaction.atomic
    def save_resource(self, data: dict) -> Resource:
        """
        Takes the serialized resource data, creates and/or updates the corresponding
        Resource object, saves and returns it.
        """
        obj = self._update_or_create_object(Resource, data)
        if obj._created:
            obj.save()
            self.logger.debug("%s created" % obj)

        # Update parents only after the resource has been created
        existing_parents = set(obj.parents.all())
        data_parents = set(data.get("parents", []))
        for parent in data_parents.difference(existing_parents):
            obj.parents.add(parent)
            obj._changed = True
            obj._changed_fields.append("parents")
        for parent in existing_parents.difference(data_parents):
            obj.parents.remove(parent)
            obj._changed = True
            obj._changed_fields.append("parents")

        # Update related origins only after the resource has been created
        data_sources = {origin["data_source_id"] for origin in data.get("origins", [])}
        for data_source in data_sources:
            data_source, created = DataSource.objects.get_or_create(id=data_source)
            if created:
                self.logger.debug("Created missing data source %s" % data_source)
        existing_origins = set(obj.origins.all())
        data_origins = set(
            [
                ResourceOrigin.objects.get_or_create(
                    resource=obj,
                    data_source_id=origin["data_source_id"],
                    origin_id=origin["origin_id"],
                )[0]
                for origin in data.get("origins", [])
            ]
        )
        for origin in data_origins.difference(existing_origins):
            origin.save()
            obj._changed = True
            obj._changed_fields.append("origins")
        for origin in existing_origins.difference(data_origins):
            origin.delete()
            obj._changed = True
            obj._changed_fields.append("origins")

        if obj._changed:
            if not obj._created:
                self.logger.debug(
                    "%s changed: %s" % (obj, ", ".join(obj._changed_fields))
                )
            obj.save()

        return obj

    @db.transaction.atomic
    def save_period(self, data: dict) -> DatePeriod:
        """Takes the serialized period data and creates a DatePeriod

        Will delete previously existing periods with the same name and dates.
        """
        try:
            time_span_groups_data = data.pop("time_span_groups")
        except KeyError:
            time_span_groups_data = []

        resource = data["resource"]

        # Delete existing date period and all time spans
        # TODO: Update existing period instead of deleting all the previous ones
        for period in DatePeriod.all_objects.filter(
            resource=resource,
            name=data["name"],
            start_date=data["start_date"],
            end_date=data["end_date"],
        ):
            for tsg in TimeSpanGroup.objects.filter(period=period):
                Rule.all_objects.filter(group=tsg).delete()
                TimeSpan.all_objects.filter(group=tsg).delete()
                tsg.delete()

            DatePeriod.all_objects.get(pk=period.id).delete()

        # Add the period as new
        date_period = DatePeriod(**data)
        date_period.save()

        for time_span_group_datum in time_span_groups_data:
            time_span_group = TimeSpanGroup(period=date_period)
            time_span_group.save()

            for time_span_datum in time_span_group_datum["time_spans"]:
                time_span_datum["group"] = time_span_group
                time_span = TimeSpan(**time_span_datum)
                time_span.save()

            for rule_datum in time_span_group_datum["rules"]:
                rule_datum["group"] = time_span_group
                rule = Rule(**rule_datum)
                rule.save()

        return date_period


importers = {}


def register_importer(klass):
    importers[klass.name] = klass
    return klass


def get_importers():
    if importers:
        return importers
    module_path = __name__.rpartition(".")[0]
    # Importing the packages will cause their register_importer() methods
    # being called.
    for fname in os.listdir(os.path.dirname(__file__)):
        module, ext = os.path.splitext(fname)
        if ext.lower() != ".py":
            continue
        if module in ("__init__", "base"):
            continue
        full_path = "%s.%s" % (module_path, module)
        ret = __import__(full_path, locals(), globals())
    return importers
