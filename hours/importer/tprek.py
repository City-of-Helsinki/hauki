import re
import time
from calendar import day_abbr, different_locale, month_name
from datetime import date
from datetime import time as datetime_time
from typing import Hashable, Tuple

import pytz
from django import db
from django.conf import settings
from django.db.models import Model
from django.db.models.signals import m2m_changed
from django_orghierarchy.models import Organization

from ..enums import ResourceType, State
from ..models import DataSource, DatePeriod, Resource
from ..signals import resource_children_changed, resource_children_cleared
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
                is_public=True,
            ),
            "connection": Resource.objects.filter(
                origins__data_source=self.data_source,
                resource_type__in=set(CONNECTION_TYPE_MAPPING.values())
                | set((ResourceType.SUBSECTION,)),
                is_public=True,
            ),
            "opening_hours": DatePeriod.objects.filter(
                origins__data_source=self.data_source,
                is_public=True,
            ),
        }
        with different_locale("fi_FI"):
            self.month_by_name = {
                name.lower(): index + 1
                for index, name in enumerate(list(month_name)[1:])
            }
            self.weekday_by_abbr = {
                abbr.lower(): index + 1 for index, abbr in enumerate(list(day_abbr))
            }

        # if we are merging objects, we must override default get_id methods
        # so that the cache and syncher merge identical connections
        if self.options.get("merge", None):
            self.get_object_id = self.merge_connections_get_object_id
            self.get_data_id = self.merge_connections_get_data_id

    def merge_connections_get_object_id(self, obj: Model) -> Hashable:
        if type(obj) == Resource and obj.resource_type in set(
            CONNECTION_TYPE_MAPPING.values()
        ) | set((ResourceType.SUBSECTION,)):
            return frozenset(obj.extra_data.items())
        return obj.origins.get(data_source=self.data_source).origin_id

    def merge_connections_get_data_id(self, data: dict) -> Hashable:
        if data.get("resource_type", None) and data["resource_type"] in set(
            CONNECTION_TYPE_MAPPING.values()
        ) | set((ResourceType.SUBSECTION,)):
            return frozenset(data["extra_data"].items())
        return [
            str(origin["origin_id"])
            for origin in data["origins"]
            if origin["data_source_id"] == self.data_source.id
        ][0]
        # Disconnect django signals for the duration of the import, to prevent huge
        # db operations at every parent add/remove
        m2m_changed.receivers = []

    @staticmethod
    def reconnect_receivers():
        # Reconnect signals at the end, in case the same runtime is used for all tests
        m2m_changed.connect(
            receiver=resource_children_changed, sender=Resource.children.through
        )
        m2m_changed.connect(
            receiver=resource_children_cleared, sender=Resource.children.through
        )

    @staticmethod
    def mark_non_public(obj: Resource) -> bool:
        obj.is_public = False
        obj.save()

    @staticmethod
    def check_non_public(obj: Resource) -> bool:
        return not obj.is_public

    def parse_dates(self, start: str, end: str) -> Tuple[date, date]:
        """
        Parses period start and end dates. If end is given, start string may be
        incomplete.
        """
        if end:
            print(month_name)
            print(list(month_name))
            print(self.month_by_name)
            print([name for name in self.month_by_name.keys()])
            print(end)
            print([name in end for name in self.month_by_name.keys()])
            if any([name in end for name in self.month_by_name.keys()]):
                # month name found
                day = int(end.split(".")[0])
                month = self.month_by_name[
                    [name for name in self.month_by_name.keys() if name in end][0]
                ]
                print(end)
                print(end[-4:])
                year = int(end[-4:])
            else:
                try:
                    day, month, year = map(int, end.split("."))
                except ValueError:
                    # end did not contain year, assume next occurrence of date
                    day = int(end.split(".")[0])
                    month = int(end.split(".")[1])
                    today = date.today()
                    if today > date(year=today.year, month=month, day=day):
                        year = today.year + 1
                    else:
                        year = today.year
            end = date(year=year, month=month, day=day)
        if start:
            print("parsing start date")
            print(start)
            print(start.split("."))
            try:
                day, month, year = map(int, start.split("."))
            except ValueError:
                try:
                    # start did not contain year
                    day = int(start.split(".")[0])
                    month = int(start.split(".")[1])
                except ValueError:
                    # start did not contain month
                    month = end.month
                try:
                    year = end.year
                except AttributeError:
                    # end did not contain year either, assume last occurrence of date
                    today = date.today()
                    if today > date(year=today.year, month=month, day=day):
                        year = today.year
                    else:
                        year = today.year - 1
            print(year)
            print(month)
            print(day)
            start = date(year=year, month=month, day=day)
        print("returning")
        print(start)
        print(end)
        return start, end

    def parse_time(self, string: str) -> datetime_time:
        if not string:
            return None
        if ":" in string:
            hour, min = map(int, string.split(":"))
        elif "." in string:
            hour, min = map(int, string.split("."))
        else:
            hour = int(string)
            min = 0
        if hour == 24:
            hour = 0
        return datetime_time(hour=hour, minute=min)

    date_regex = r"([0-3])?[0-9]\.(10|11|12|[0-9])\.([0-9]{4})?"
    date_optional_month_regex = r"([0-3])?[0-9]\.((10|11|12|[0-9])\.([0-9]{4})?)?"
    date_or_span_regex = r"([0-3])?[0-9]\.(10|11|12|[0-9])\.([0-9]{4})?(-([0-3])?[0-9]\.(10|11|12|[0-9])\.[0-9]{4})?"  # noqa
    weekday_or_span_regex = r"([a-z][a-z])(-([a-z][a-z]))?"
    time_regex = r"[0-9][0-9](:[0-9][0-9])?"

    def parse_period_string(self, string: str) -> list:
        """
        Takes TPREK simple Finnish opening hours string and returns any period data
        (start and end dates), or semi-infinite period if no dates found.
        """
        periods = []
        potential_period_strs = string.split(",")
        previous_period_str = ""
        # if we have no match, the default period starts today
        start_date = date.today()
        end_date = None
        for index, potential_period_str in enumerate(potential_period_strs):
            # match to pattern with one or two dates, e.g. 1.12.2020 or 5.-10.12.2020
            # or 12.12.2020 asti
            # https://regex101.com/r/UkhZ4e/4
            pattern = re.compile(
                r"(alkaen )?([0-3]?[0-9]\.((((10|11|12|[0-9])\.|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)|(\s)?-(\s)?))((\s)?-(\s)?)?(([0-3]?[0-9])\.((10|11|12|[0-9])\.|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)?( alkaen| asti)?",  # noqa
                re.IGNORECASE,
            )

            match = pattern.search(potential_period_str)
            if match:
                # in case of date match, save previous strings as a separate period
                print("match found")
                print("previous string is")
                print(previous_period_str)
                if previous_period_str:
                    print("appending period")
                    if "poikkeuksellisesti" in previous_period_str:
                        override = True
                    else:
                        override = False
                    periods.append(
                        {
                            "start_date": start_date,
                            "end_date": end_date,
                            "string": previous_period_str.lower(),
                            "override": override,
                            "resource_state": State.UNDEFINED,
                        }
                    )
                    print(periods)
                    # string has been saved, do not use the string for the next period
                    previous_period_str = ""
                print("adding match")
                print(potential_period_str)
                print(match)
                if match.group(14):
                    print("two dates")
                    # two dates found, start and end!
                    start_date, end_date = self.parse_dates(
                        match.group(2), match.group(14)
                    )
                    # end_date = self.parse_date(match.group(9))
                else:
                    print("only one date")
                    if (match.group(1) and "alkaen" in match.group(1)) or (
                        match.group(20) and "alkaen" in match.group(20)
                    ):
                        # starting date known
                        print("only start date known")
                        start_date, end_date = self.parse_dates(match.group(2), None)
                    elif match.group(20) and "asti" in match.group(20):
                        # end date known
                        start_date, end_date = self.parse_dates(None, match.group(2))
                    else:
                        # single day exception
                        start_date, end_date = self.parse_dates(
                            match.group(2), match.group(2)
                        )

            # paste strings together whether match is found or not
            if previous_period_str:
                previous_period_str += ","
            previous_period_str += potential_period_str
            print("previous string is now")
            print(previous_period_str)
            if index < len(potential_period_strs) - 1:
                # no need to save yet, more will follow
                continue
            else:
                # end of the loop without matching, use the pasted string
                print("appending period")
                if "poikkeuksellisesti" in previous_period_str:
                    override = True
                else:
                    override = False
                periods.append(
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "override": override,
                        "string": previous_period_str.lower(),
                        "resource_state": State.UNDEFINED,
                    }
                )
            print(periods)
            # string has been saved, do not use the string for the next period
            previous_period_str = ""
        return periods

    def parse_opening_string(self, string: str) -> dict:
        """
        Takes TPREK simple Finnish opening hours string and returns corresponding
        opening time spans, if found.
        """
        time_spans = []
        # match to single span, e.g. ma-pe 8-16:30 or suljettu pe or joka päivä 07-
        # https://regex101.com/r/UkhZ4e/13
        pattern = re.compile(
            r"((suljettu|avoinna)(\spoikkeuksellisesti)?|huoltotauko|\sja)?(\s([0-3])?[0-9]\.((10|11|12|[0-9])\.([0-9]{4})?)?(\s?-\s?([0-3])?[0-9]\.(10|11|12|[0-9])\.([0-9]{4})?)?)?\s?-?\s?((\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su]))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?|\s([0-3])?[0-9]\.((10|11|12|[0-9])\.([0-9]{4})?)?)|joka päivä|päivittäin)(\s([0-3])?[0-9]\.((10|11|12|[0-9])\.([0-9]{4})?)?)?(\s|$)(ke?ll?o\s)*(([0-2]?[0-9]((\.|:)[0-9][0-9])?)((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?(((,|\sja)?\s[0-2]?[0-9]((\.|:)[0-9][0-9])?)((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?)?|suljettu|ympäri vuorokauden)?(\s(alkaen|asti))?",  # noqa
            re.IGNORECASE,
        )
        # 1) standardize formatting to get single whitespaces everywhere
        # 2) standardize dashes
        string = " " + " ".join(string.split()).replace("−", "-")
        print(string)
        matches = pattern.finditer(string)
        print("we have the matches:")
        if not matches:
            # TODO: do this in period if no time spans
            # no weekdays and times specified, resource might be closed
            if "suljettu" in string:
                time_spans.append(
                    {
                        "group": None,
                        "start_time": None,
                        "end_time": None,
                        "weekdays": None,
                        "resource_state": State.CLOSED,
                        "full_day": True,
                    }
                )

        for match in matches:
            print(match)
            # If we have no weekday matches, assume daily opening
            if not match.group(15) or "joka päivä" in match.group(14):
                weekdays = None
            else:
                start_weekday = self.weekday_by_abbr[match.group(15).lower()]
                if match.group(17):
                    end_weekday = self.weekday_by_abbr[match.group(17).lower()]
                    weekdays = list(range(start_weekday, end_weekday + 1))
                else:
                    weekdays = [start_weekday]
                # TODO: we might have three more tuples of weekdays, if we're really
                # unlucky :(

            if (match.group(2) and "suljettu" in match.group(2)) or (
                match.group(44) and "suljettu" in match.group(44)
            ):
                print("suljettu found")
                start_time = None
                end_time = None
                resource_state = State.CLOSED
                full_day = True
            elif match.group(66) == "asti":
                start_time = datetime_time(hour=0, minute=0)
                end_time = self.parse_time(match.group(45))
                resource_state = State.OPEN
                full_day = False
            else:
                # TODO: we might have two time spans, if we're really unlucky :(
                start_time = self.parse_time(match.group(45))
                end_time = self.parse_time(match.group(51))
                if not end_time:
                    end_time = datetime_time(hour=0, minute=0)
                resource_state = State.OPEN
                full_day = False

            time_spans.append(
                {
                    "group": None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "weekdays": weekdays,
                    "resource_state": resource_state,
                    "full_day": full_day,
                }
            )
            # no need to consider past strings any more
            # previous_time_span_str = ""

        print(time_spans)
        return time_spans

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
            "timezone": pytz.timezone("Europe/Helsinki"),
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
        connection_id = str(data.pop("connection_id"))
        unit_id = str(data.pop("unit_id"))
        origin = {
            "data_source_id": self.data_source.id,
            "origin_id": connection_id,
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

    def get_opening_hours_data(self, data: dict) -> list:
        """
        Takes connection data dict in TPREK v4 API format and returns the corresponding
        serialized DatePeriods.
        """
        # Running id will be removed once tprek adds permanent ids to their API.
        if "id" not in data:
            data["id"] = int(time.time() * 100000)
        connection_id = str(data.pop("id"))
        unit_id = str(data.pop("unit_id"))
        # resource may be missing if e.g. the unit has just been created or
        # deleted, or is not public at the moment. Therefore, resource may be empty.
        # TODO: in case we are importing hours in non-opening hours connection, add them
        # to the original connection instead, not the unit!
        print("trying to find resource with id")
        print(unit_id)
        resource = self.resource_cache.get(unit_id, None)
        print("found resource")
        print(resource)
        period_string = data.get("name_fi", "")
        if not period_string:
            print(
                "Error parsing data, Finnish opening hours not found! {0}".format(data)
            )
        try:
            periods = self.parse_period_string(period_string)
        except ValueError:
            print(
                "Error parsing string, most likely dates are invalid! {0}".format(
                    period_string
                )
            )
            periods = []
        data = []
        for period in periods:
            try:
                time_spans = self.parse_opening_string(period["string"])
            except ValueError:
                print(
                    "Error parsing period, most likely delimiters are missing! "
                    + "{0}".format(period)
                )
                continue
            print(time_spans)
            if (
                not time_spans
                or all([span["resource_state"] == State.CLOSED for span in time_spans])
            ) and "suljettu" in period["string"]:
                print("all time spans closed")
                resource_state = State.CLOSED
            elif (
                not time_spans
                and "avoinna" in period["string"]
                and "suljettu" not in period["string"]
            ):
                resource_state = State.OPEN
            elif (
                "suljettu" not in period["string"]
                and "joka päivä" in period["string"]
                and "ympäri vuorokauden" in period["string"]
            ):
                resource_state = State.OPEN
            else:
                resource_state = State.UNDEFINED

            start_date = period.get("start_date", date.today())
            end_date = period.get("end_date", None)
            origin = {
                "data_source_id": self.data_source.id,
                "origin_id": "connection-{0}-{1}".format(connection_id, start_date),
            }
            period_datum = {
                "resource": resource,
                "start_date": start_date,
                "end_date": end_date,
                "override": period["override"],
                "resource_state": resource_state,
                "origins": [origin],
                "time_span_groups": [
                    {
                        "time_spans": time_spans,
                        "rules": [],
                    }
                ],
            }
            data.append(period_datum)
        print(data)
        return data

    def filter_opening_hours_data(self, data: list) -> list:
        """
        Takes connection data list and filters the connections that should be imported.
        """
        return [
            connection
            for connection in data
            if connection["section_type"] == "OPENING_HOURS"
        ]

    @db.transaction.atomic
    def import_objects(
        self,
        object_type: str,
    ):
        """
        Imports objects of the given type, using get_object_id and get_data_id
        to match incoming data with existing objects. The default id function is
        the origin_id of the object in this data source. Object id may be any
        hashable that can be used to index objects and implements __eq__. Objects
        with the same identifier will be merged.
        """
        queryset = self.data_to_match[object_type]
        klass_str = queryset.model.__name__.lower()
        api_object_type = (
            "connection" if object_type == "opening_hours" else object_type
        )

        api_params = {
            "official": "yes",
        }
        if object_type == "connection":
            api_params["connectionmode"] = "hauki"

        if self.options.get("single", None):
            obj_id = self.options["single"]
            obj_list = [self.api_get(api_object_type, obj_id, params=api_params)]
            self.logger.info("Loading TPREK " + object_type + " " + str(obj_list))
            queryset = queryset.filter(
                origins__data_source=self.data_source, origins__origin_id=obj_id
            )
        else:
            self.logger.info("Loading TPREK " + object_type + "s...")
            obj_list = self.api_get(object_type, params=api_params)
        syncher = ModelSyncher(
            queryset,
            self.get_object_id,
            delete_func=self.mark_non_public,
            check_deleted_func=self.check_non_public,
        )
        obj_list = getattr(self, "filter_%s_data" % object_type)(obj_list)
        self.logger.info("%s %ss loaded" % (len(obj_list), object_type))
        obj_dict = {}
        for idx, data in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss read" % (idx, object_type))
            object_data = getattr(self, "get_%s_data" % object_type)(data)
            print("generating ids for data")
            print(object_data)
            if not isinstance(object_data, list):
                # wrap single objects in list, because object_data may also contain
                # multiple objects
                object_data = [object_data]
            for datum in object_data:
                # TODO: multiple ids from datum
                object_data_id = self.get_data_id(datum)
                if object_data_id not in obj_dict:
                    obj_dict[object_data_id] = datum
                else:
                    # Duplicate object found. Just append its foreign keys instead of
                    # adding another object.
                    parents = datum["parents"]
                    origins = datum["origins"]
                    self.logger.info(
                        "Adding duplicate parent %s and origin %s to object %s"
                        % (parents, origins, object_data_id)
                    )
                    obj_dict[object_data_id]["parents"].extend(parents)
                    obj_dict[object_data_id]["origins"].extend(origins)
        for idx, object_data in enumerate(obj_dict.values()):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss saved" % (idx, object_type))
            obj = getattr(self, f"save_{klass_str}")(object_data)

            syncher.mark(obj)

        syncher.finish(force=self.options["force"])
        self.reconnect_receivers()

    @db.transaction.atomic
    def import_units(self):
        self.logger.info("Importing TPREK units")
        self.import_objects("unit")

    @db.transaction.atomic
    def import_connections(self):
        self.logger.info("Importing TPREK connections")
        if self.options.get("merge", None):
            self.logger.info("Merging identical connections")
        self.import_objects("connection")

    def import_resources(self):
        self.import_units()
        self.import_connections()

    def import_openings(self):
        self.logger.info("Importing TPREK opening hours")
        self.import_objects("opening_hours")
