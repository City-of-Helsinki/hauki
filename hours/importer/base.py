import logging
import os
import re
from collections.abc import Sized
from itertools import zip_longest

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

        self.logger.info("Caching existing resources from db")
        self.resource_cache = {}
        for obj in (
            Resource.objects.filter(origins__data_source=self.data_source)
            .distinct()
            .prefetch_related("origins")
        ):
            obj_id = self.get_object_id(obj)
            if obj_id in self.resource_cache:
                if not self.options["force"]:
                    raise Exception(
                        f"Multiple objects with an identical generated id"
                        f" {self.get_object_id(obj)} found in database."
                        f" Most likely you are running the importer with the --merge"
                        f" parameter while having separate non-merged objects in"
                        f" database already. Merging will add their origin_ids to"
                        f" the first object and delete duplicates, along with their"
                        f" opening hours. If you are sure you want to do that,"
                        f" please run the importer with the parameters --merge"
                        f" --force."
                    )
            self.resource_cache[obj_id] = obj

        self.logger.info("Caching existing date periods from db")
        self.dateperiod_cache = {
            self.get_object_id(obj): obj
            for obj in DatePeriod.objects.filter(
                origins__data_source=self.data_source
            ).prefetch_related("origins")
        }

    def get_object_id(self, obj: Model) -> str:
        try:
            return obj.origins.get(data_source=self.data_source).origin_id
        except MultipleObjectsReturned:
            if self.options.get("force", None):
                return obj.origins.filter(data_source=self.data_source)[0].origin_id
            else:
                raise Exception(
                    f"Seems like your database already contains multiple origin_ids"
                    f" for {obj} from data source {self.data_source}. This is the"
                    f" result of running an importer with the --merge parameter."
                    f" Please run the importer with --merge to combine identical"
                    f" objects into one, or --force to un-merge any previously"
                    f" combined objects. Their opening hours will only apply for"
                    f" one of the un-merged objects from now on, and others will"
                    f" not have opening data."
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

    def mark_deleted(self, obj: SoftDeletableModel) -> bool:
        # SoftDeletableModel does not return anything when *soft* deleting
        obj.delete()

    def check_deleted(self, obj: SoftDeletableModel) -> bool:
        return obj.is_removed

    @staticmethod
    def clean_text(text: str, strip_newlines: bool = False) -> str:
        # remove non-breaking spaces and separators
        text = text.replace("\xa0", " ").replace("\x1f", "")
        # remove nil bytes
        text = text.replace("\u0000", " ")
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
    ) -> Model:
        """
        Takes the class and serialized data, creates and/or updates the Model
        object, saves and returns it saved for class-specific processing.
        """
        # look for existing object
        klass_str = klass.__name__.lower()
        cache = getattr(self, "%s_cache" % klass_str)
        obj_id = self.get_data_id(data)
        obj = cache.get(obj_id, None)
        if obj:
            obj._created = False
        else:
            obj = klass()
            obj._created = True
            # save the new object in the cache so related objects will find it
            setattr(
                self,
                "%s_cache" % klass_str,
                {**cache, **{obj_id: obj}},
            )
        obj._changed = False
        obj._changed_fields = []

        self._update_fields(obj, data)
        self._set_field(obj, "is_removed", False)
        self._set_field(obj, "is_public", True)  # always set resource public at save

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
        object_origins = set(obj.origins.all())
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
        for origin in data_origins.difference(object_origins):
            origin.save()
            obj._changed = True
            obj._changed_fields.append("origins")
        for origin in object_origins.difference(data_origins):
            # object origins are prefetched, so we must double-check origin
            # hasn't already moved to another object:
            if (
                getattr(
                    klass.origins.field.model.objects.get(id=origin.id),
                    klass.origins.field.name,
                )
                == obj
            ):
                origin.delete()
            obj._changed = True
            obj._changed_fields.append("origins")
        return obj

    @db.transaction.atomic
    def save_resource(
        self,
        data: dict,
    ) -> Resource:
        """
        Takes the serialized resource data, creates and/or updates the corresponding
        Resource object, and returns it.

        get_data_id can be used to match incoming data with existing objects. The
        default id function is the origin_id of the object in this data source. Object
        id may be any hashable that can be used to index objects and implements __eq__.
        Objects must have unique ids.
        """

        obj = self._update_or_create_object(Resource, data)

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
            # Child ancestry should be updated after they get parents.
            # At this point, obj will not yet have children to update.
            obj.save(update_child_ancestry_fields=False)
            # It has all the necessary parents, on the other hand.
            if "parents" in obj._changed_fields:
                obj.update_ancestry()

        return obj

    @db.transaction.atomic
    def save_dateperiod(
        self,
        data: dict,
    ) -> DatePeriod:
        """Takes the serialized period data, creates and/or updates the corresponding
        DatePeriod object, and returns it.
        """

        period = self._update_or_create_object(DatePeriod, data)
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
