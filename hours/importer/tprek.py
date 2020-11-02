import time
from typing import Callable, Hashable

from django import db
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Model
from django_orghierarchy.models import Organization

from ..enums import ResourceType
from ..models import DataSource, Resource
from .base import Importer, register_importer
from .sync import ModelSyncher

# Here we list which tprek connection types should be mapped to which resource types.
# Absent an entry in the mapping, the default for connections is "SUBSECTION".
CONNECTION_TYPE_MAPPING = {
    "LINK": ResourceType.ONLINE_SERVICE,
    "ESERVICE_LINK": ResourceType.ONLINE_SERVICE,
    "PHONE_OR_EMAIL": ResourceType.CONTACT,
    "OTHER_ADDRESS": ResourceType.ENTRANCE,
    "TOPICAL": ResourceType.SUBSECTION,
    "HIGHLIGHT": ResourceType.SUBSECTION,
    "OTHER_INFO": ResourceType.SUBSECTION,
}

# here we list the tprek connection types that we do *not* want to use in Hauki
CONNECTION_TYPES_TO_IGNORE = ["OPENING_HOURS", "SOCIAL_MEDIA_LINK"]


@register_importer
class TPRekImporter(Importer):
    name = "tprek"

    def setup(self):
        self.URL_BASE = "http://www.hel.fi/palvelukarttaws/rest/v4/"
        # The urls below are only used for constructing extra links for each unit
        self.ADMIN_URL_BASE = (
            "https://asiointi.hel.fi/tprperhe/TPR/UI/ServicePoint/ServicePointEdit/"
        )
        self.CITIZEN_URL_BASE = "https://palvelukartta.hel.fi/fi/unit/"
        ds_args = dict(id="tprek")
        defaults = dict(name="Toimipisterekisteri")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )
        # this maps the imported resource names to Hauki objects
        self.data_to_match = {
            "unit": Resource.objects.filter(
                origins__data_source=self.data_source,
                resource_type=ResourceType.UNIT,
            ),
            "connection": Resource.objects.filter(
                origins__data_source=self.data_source,
                resource_type__in=set(CONNECTION_TYPE_MAPPING.values())
                | set((ResourceType.SUBSECTION,)),
            ),
        }

    def get_unit_origins(self, data: dict) -> list:
        """
        Takes unit data dict in TPREK v4 API format and returns the
        corresponding serialized ResourceOrigin data
        """
        origins = []

        # tprek external identifier is always an origin
        origins.append(
            {"data_source_id": self.data_source.id, "origin_id": str(data["id"])}
        )

        if "sources" in data:
            for source in data["sources"]:
                # do *not* store tprek internal identifier, we want nothing to do
                # with it
                if source["source"] == "internal":
                    continue
                origin = {
                    "data_source_id": source["source"],
                    "origin_id": str(source["id"]),
                }
                origins.append(origin)
        return origins

    def get_unit_links(self, data: dict) -> dict:
        """
        Takes unit data dict in TPREK v4 API format and returns the
        corresponding link URLs
        """
        links = {}

        # use tprek external identifier for constructing the service map link
        links["citizen_url"] = self.CITIZEN_URL_BASE + str(data["id"])

        if "sources" in data:
            for source in data["sources"]:
                # use tprek internal identifier for constructing the TPREK admin link
                if source["source"] == "internal":
                    links["admin_url"] = self.ADMIN_URL_BASE + str(source["id"])
                else:
                    continue
        return links

    def get_multilanguage_string(self, field_name: str, data: dict) -> dict:
        """
        Takes unit data dict and returns the multilanguage dict for given field.
        """
        return {
            lang[0]: self.clean_text(data.get("%s_%s" % (field_name, lang[0]), ""))
            for lang in settings.LANGUAGES
        }

    def get_unit_address(self, data: dict) -> dict:
        """
        Takes unit data dict and constructs address in each language.
        """
        address = {}
        for lang in settings.LANGUAGES:
            address[lang[0]] = self.clean_text(
                data.get("street_address_%s" % lang[0], "")
                + ", "
                + data.get("address_city_%s" % lang[0], "")
            )
        return address

    def get_resource_name(self, data: dict) -> dict:
        """
        Takes resource data dict and returns name in each language, limited to 255
        characters.
        """
        return {
            lang: name[:255]
            for lang, name in self.get_multilanguage_string("name", data).items()
        }

    def get_unit_data(self, data: dict) -> dict:
        """
        Takes unit data dict in TPREK v4 API format and returns the corresponding
        serialized Resource data.
        """
        obj_organization, created = Organization.objects.get_or_create(
            data_source=self.data_source, origin_id=data["dept_id"]
        )
        if created:
            self.logger.debug("Created missing organization tprek:%s" % data["dept_id"])
        unit_data = {
            "origins": self.get_unit_origins(data),
            "resource_type": ResourceType.UNIT,
            "name": self.get_resource_name(data),
            "description": self.get_multilanguage_string("desc", data),
            "address": self.get_unit_address(data),
            "same_as": self.get_url("unit", data["id"]),
            "organization": obj_organization,
            "extra_data": self.get_unit_links(data),
        }
        return unit_data

    def filter_unit_data(self, data: list) -> list:
        """
        Takes unit data list and filters the units that should be imported.
        """
        # currently, all units are imported
        return data

    def get_connection_description(self, data: dict) -> dict:
        """
        Takes connection data dict and returns a suitable description parsed from the
        various text fields.
        """
        description = {}
        for lang in settings.LANGUAGES:
            description[lang[0]] = self.clean_text(
                data.get("contact_person", "")
                + " "
                + data.get("email", "")
                + " "
                + data.get("phone", "")
                + " "
                + data.get("www_%s" % lang[0], "")
            )
            # Name sometimes contains stuff that better fits description, plus name may
            # be cut short, plus constructed description may be empty anyway
            if not description[lang[0]]:
                description[lang[0]] = self.clean_text(
                    data.get("name_%s" % lang[0], "")
                )
        return description

    def get_connection_data(self, data: dict) -> dict:
        """
        Takes connection data dict in TPREK v4 API format and returns the corresponding
        serialized Resource data.
        """
        # Running id will be removed once tprek adds permanent ids to their API.
        if "id" not in data:
            data["id"] = int(time.time() * 100000)
        connection_id = str(data.pop("id"))
        unit_id = str(data.pop("unit_id"))
        origin = {
            "data_source_id": self.data_source.id,
            "origin_id": "connection-%s" % connection_id,
        }
        # parent may be missing if e.g. the unit has just been created or
        # deleted, or is not public at the moment. Therefore, parent may be empty.
        parent = self.resource_cache.get(unit_id, None)
        parents = [parent] if parent else []
        # incoming data will be saved raw in extra_data, to allow matching identical
        # connections
        connection_data = {
            "origins": [origin],
            "resource_type": CONNECTION_TYPE_MAPPING[data["section_type"]],
            "name": self.get_resource_name(data),
            "description": self.get_connection_description(data),
            "address": self.get_resource_name(data)
            if CONNECTION_TYPE_MAPPING[data["section_type"]] == ResourceType.ENTRANCE
            else "",
            "parents": parents,
            "extra_data": data,
        }

        return connection_data

    def filter_connection_data(self, data: list) -> list:
        """
        Takes connection data list and filters the connections that should be imported.
        """
        return [
            connection
            for connection in data
            if connection["section_type"] not in CONNECTION_TYPES_TO_IGNORE
        ]

    @db.transaction.atomic
    def import_objects(
        self,
        object_type: str,
        get_object_id: Callable[[Model], Hashable] = None,
        get_data_id: Callable[[dict], Hashable] = None,
    ):
        """
        Imports objects of the given type, using get_object_id and get_data_id
        to match incoming data with existing objects. The default id function is
        the origin_id of the object in this data source. Object id may be any
        hashable that can be used to index objects and implements __eq__. Objects
        with the same identifier will be merged.
        """
        queryset = self.data_to_match[object_type]
        if not get_object_id and not get_data_id:

            def get_object_id(obj: Model) -> str:
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

            def get_data_id(data: dict) -> str:
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

        else:
            if not get_object_id or not get_data_id:
                raise Exception(
                    "Both get_object_id and get_data_id functions must be provided"
                    " to match existing objects to incoming data."
                )

        syncher = ModelSyncher(
            queryset,
            get_object_id,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )

        if self.options.get("single", None):
            obj_id = self.options["single"]
            obj_list = [self.api_get(object_type, obj_id, params={"official": "yes"})]
            queryset = queryset.filter(id=obj_id)
        else:
            self.logger.info("Loading TPREK " + object_type + "s...")
            obj_list = self.api_get(object_type, params={"official": "yes"})
            self.logger.info("%s %ss loaded" % (len(obj_list), object_type))
        obj_list = getattr(self, "filter_%s_data" % object_type)(obj_list)
        obj_dict = {}
        for idx, data in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss read" % (idx, object_type))
            object_data = getattr(self, "get_%s_data" % object_type)(data)
            object_data_id = get_data_id(object_data)
            if object_data_id not in obj_dict:
                obj_dict[object_data_id] = object_data
            else:
                # Duplicate object found. Just append its foreign keys instead of
                # adding another object.
                parents = object_data["parents"]
                origins = object_data["origins"]
                self.logger.debug(
                    "Adding duplicate object foreign keys %s to object %s"
                    % ((parents, origins), object_data_id)
                )
                obj_dict[object_data_id]["parents"].extend(parents)
                obj_dict[object_data_id]["origins"].extend(origins)
        for idx, object_data in enumerate(obj_dict.values()):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss saved" % (idx, object_type))
            obj = self.save_resource(object_data)

            syncher.mark(obj)

        syncher.finish(force=self.options["force"])

    @db.transaction.atomic
    def import_units(self):
        self.logger.info("Importing TPREK units")
        self.import_objects("unit")

    @db.transaction.atomic
    def import_connections(self):
        self.logger.info("Importing TPREK connections")
        if self.options.get("merge", None):
            self.logger.info("Merging identical connections")
            # Merge connections if their extra_data is identical.
            # Extra_data contains all data apart from origin and parent.
            self.import_objects(
                "connection",
                get_object_id=lambda obj: frozenset(obj.extra_data.items()),
                get_data_id=lambda data: frozenset(data["extra_data"].items()),
            )
        else:
            self.import_objects("connection")

    def import_resources(self):
        self.import_units()
        self.import_connections()
