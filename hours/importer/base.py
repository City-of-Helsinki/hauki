import logging
import os
import re
from collections.abc import Sized
from itertools import zip_longest
from typing import Callable, Hashable

import requests
from django import db
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Model
from model_utils.models import SoftDeletableModel
from modeltranslation.translator import translator

from hours.models import DataSource, DatePeriod, Resource, Rule, TimeSpan, TimeSpanGroup


class Importer(object):
    def __init__(self, options):
        self.logger = logging.getLogger("%s_importer" % self.name)
        self.options = options
        self.setup()
        # The cache needs to be populated by each consecutive import command
        # if we want to match and link to existing and newly imported data.
        # If resource_cache remains empty, new objects without foreign keys
        # will be created.
        self.resource_cache = {}
        self.dateperiod_cache = {}

    def get_object_id(self, obj: Model) -> str:
        try:
            return obj.origins.get(data_source=self.data_source).origin_id
        except MultipleObjectsReturned:
            raise Exception(
                "Seems like your database already contains multiple identifiers"
                " for the same object in importer data source. Please run the"
                " importer with --merge to combine identical objects into one,"
                " or remove the duplicate origin_ids in the database before"
                " trying to import identical connections as separate objects."
            )

    def get_data_id(self, data: dict) -> str:
        origin_ids = [
            str(origin["origin_id"])
            for origin in data["origins"]
            if origin["data_source_id"] == self.data_source.id
        ]
        if len(origin_ids) > 1:
            raise Exception(
                "Seems like your data contains multiple identifiers in the"
                " same object in importer data source. Please provide"
                " get_object_id and get_data_id methods to return a single"
                " hashable identifier to use for identifying objects."
            )
        return origin_ids[0]

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
        # SoftDeletableModel does not return anything when *soft* deleting
        obj.delete()

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

    def _update_or_create_object(
        self,
        klass: type,
        data: dict,
        get_data_id: Callable[[dict], Hashable],
    ) -> Model:
        """
        Takes the class and serialized data, creates and/or updates the Model
        object, saves and returns it saved for class-specific processing.
        """
        # look for existing object
        cache = getattr(self, "%s_cache" % klass.__name__.lower())
        obj_id = get_data_id(data)
        obj = cache.get(obj_id, None)
        if obj:
            obj._created = False
        else:
            obj = klass()
            obj._created = True
            # save the new object in the cache so related objects will find it
            setattr(
                self,
                "%s_cache" % klass.__name__.lower(),
                {**cache, **{obj_id: obj}},
            )
        obj._changed = False
        obj._changed_fields = []

        self._update_fields(obj, data)
        self._set_field(obj, "is_removed", False)
        self._set_field(obj, "is_public", True)

        # required fields are filled, so the object may be saved now
        if obj._created:
            obj.save()
            self.logger.info("%s created" % obj)

        # Update object origins only after the object has been saved
        data_sources = {origin["data_source_id"] for origin in data.get("origins", [])}
        for data_source in data_sources:
            data_source, created = DataSource.objects.get_or_create(id=data_source)
            if created:
                self.logger.debug("Created missing data source %s" % data_source)
        existing_origins = set(obj.origins.all())
        data_origins = set(
            [
                klass.origins.field.model.objects.get_or_create(
                    data_source_id=origin["data_source_id"],
                    origin_id=origin["origin_id"],
                    defaults={klass.origins.field.name: obj},
                )[0]
                for origin in data.get("origins", [])
            ]
        )
        # Any existing origins referring to other objects must be updated
        for origin in data_origins:
            setattr(origin, klass.origins.field.name, obj)
        for origin in data_origins.difference(existing_origins):
            origin.save()
            obj._changed = True
            obj._changed_fields.append("origins")
        for origin in existing_origins.difference(data_origins):
            # Removing an extra origin is the only way origins may be deleted.
            # Soft deleted objects will retain their old origins.
            origin.delete()
            obj._changed = True
            obj._changed_fields.append("origins")
        return obj

    @db.transaction.atomic
    def save_resource(
        self,
        data: dict,
        get_data_id: Callable[[dict], Hashable] = None,
    ) -> Resource:
        """
        Takes the serialized resource data, creates and/or updates the corresponding
        Resource object, and returns it.

        get_data_id can be used to match incoming data with existing objects. The
        default id function is the origin_id of the object in this data source. Object
        id may be any hashable that can be used to index objects and implements __eq__.
        Objects must have unique ids.
        """
        if not get_data_id:
            # Default origin_ids will be used
            get_data_id = self.get_data_id

        obj = self._update_or_create_object(Resource, data, get_data_id)

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

        if obj._changed:
            if not obj._created:
                self.logger.info(
                    "%s changed: %s" % (obj, ", ".join(obj._changed_fields))
                )
            obj.save()

        return obj

    @db.transaction.atomic
    def save_period(self, data: dict) -> DatePeriod:
        """Takes the serialized period data, creates and/or updates the corresponding
        DatePeriod object, and returns it.
        """
        period = self._update_or_create_object(DatePeriod, data, self.get_data_id)
        try:
            time_span_groups_data = data.pop("time_span_groups")
        except KeyError:
            time_span_groups_data = []

        # if data didn't change, the time span groups will be in db order
        existing_time_span_groups = period.time_span_groups.all()
        for datum, existing_group in zip_longest(
            time_span_groups_data, existing_time_span_groups, fillvalue=None
        ):
            if not datum:
                existing_group.delete()
                period._changed = True
                period._changed_fields.append("time_span_groups")
                continue
            elif not existing_group:
                time_span_group = TimeSpanGroup(period=period)
                time_span_group.save()
                period._changed = True
                period._changed_fields.append("time_span_groups")
                existing_time_spans = ()
                existing_rules = ()
            else:
                time_span_group = existing_group
                existing_time_spans = existing_group.time_spans.all()
                existing_rules = existing_group.rules.all()

            # if data didn't change, the time spans will be in db order
            for time_span_datum, existing_time_span in zip_longest(
                datum["time_spans"], existing_time_spans, fillvalue=None
            ):
                if not time_span_datum:
                    existing_time_span.delete()
                    period._changed = True
                    period._changed_fields.append("time_span_groups__time_span")
                    continue
                elif not existing_time_span:
                    time_span_datum["group"] = time_span_group
                    time_span = TimeSpan(**time_span_datum)
                    time_span.save()
                    period._changed = True
                    period._changed_fields.append("time_span_groups__time_span")
                else:
                    time_span_datum["group"] = time_span_group
                    existing_time_span._changed = False
                    self._update_fields(existing_time_span, time_span_datum)
                    if existing_time_span._changed:
                        period._changed = True
                        period._changed_fields.append("time_span_groups__time_span")
                        existing_time_span.save()

            # if data didn't change, the rules will be in db order
            for rule_datum, existing_rule in zip_longest(
                datum["rules"], existing_rules, fillvalue=None
            ):
                if not rule_datum:
                    existing_rule.delete()
                    period._changed = True
                    period._changed_fields.append("time_span_groups__rule")
                    continue
                elif not existing_rule:
                    rule_datum["group"] = time_span_group
                    rule = Rule(**rule_datum)
                    rule.save()
                    period._changed = True
                    period._changed_fields.append("time_span_groups__rule")
                else:
                    rule_datum["group"] = time_span_group
                    existing_rule._changed = False
                    self._update_fields(existing_rule, rule_datum)
                    if existing_rule._changed:
                        period._changed = True
                        period._changed_fields.append("time_span_groups__rule")
                        existing_rule.save()

        if period._changed:
            if not period._created:
                self.logger.info(
                    "%s changed: %s" % (period, ", ".join(period._changed_fields))
                )
            period.save()

        return period


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
