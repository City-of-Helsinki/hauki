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

# here we list the tprek connection types that we do *not* want to import as resources
CONNECTION_TYPES_TO_IGNORE = {"OPENING_HOURS", "SOCIAL_MEDIA_LINK"}

# https://regex101.com/r/HOIX1L/4
date_or_span_regex = r"(alkaen\s)?(([0-3]?[0-9])\.(((10|11|12|[0-9])(\.|\s)|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)?(\s)?-(\s)?)?(([0-3]?[0-9])\.((10|11|12|[0-9])(\.|\s)|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)(\salkaen|\sasti)?"  # noqa
date_optional_month_regex = (
    r"(alkaen\s)?([0-3])?[0-9]\.((10|11|12|[0-9])\.?([0-9]{4})?)?"  # noqa
)
multiple_weekday_spans_regex = r"(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su]))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?"  # noqa
multiple_time_spans_regex = r"([0-2]?[0-9]((\.|:)[0-9][0-9])?)((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?(((,|\sja)?\s([0-2]?[0-9]((\.|:)[0-9][0-9])?))((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?)?"  # noqa


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
        ds_args = dict(id="kirkanta")
        defaults = dict(name="kirjastot.fi")
        self.kirjastot_data_source, _ = DataSource.objects.get_or_create(
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
            ).exclude(origins__data_source=self.kirjastot_data_source),
        }
        with different_locale("fi_FI.utf-8"):
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

    @staticmethod
    def disconnect_receivers():
        # Disconnect django signals for the duration of the import, to prevent huge
        # db operations at every parent add/remove, plus possible race conditions
        # which freeze the import intermittently
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
            if any([name in end for name in self.month_by_name.keys()]):
                # month name found
                day = int(end.split(".")[0])
                month = self.month_by_name[
                    [name for name in self.month_by_name.keys() if name in end][0]
                ]
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
                if end and month <= end.month:
                    # only use end year if start month is before end month
                    year = end.year
                else:
                    # end did not contain year either, assume last occurrence of date
                    today = date.today()
                    if today > date(year=today.year, month=month, day=day):
                        year = today.year
                    else:
                        year = today.year - 1
            start = date(year=year, month=month, day=day)
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

    def parse_period_string(self, string: str) -> list:
        """
        Takes TPREK simple Finnish opening hours string and returns any period data
        (start and end dates), or semi-infinite period if no dates found.
        """
        periods = []
        # Split the whole string using date pattern.
        # match to pattern with one or two dates, e.g. 1.12.2020 or 5.-10.12.2020
        # or 12.12.2020 asti
        pattern = re.compile(date_or_span_regex, re.IGNORECASE)

        # 1) get rid of multiple newlines
        string = string.replace("\n\n", "\n")
        # 2) add any missing spaces after commas
        string = re.sub(r",([^\s])", lambda match: ", " + match.group(1), string)
        # 3) standardize formatting to use comma + whitespace instead of newlines
        # 4) start all period strings with whitespace
        string = " " + ", ".join(string.splitlines())
        # 5) standardize formatting to lowercase
        string = string.lower()

        matches = list(pattern.finditer(string))

        # no matches => just use the whole string
        if not matches:
            strings = [string]
        # one or more matches => one or more date periods
        else:
            strings = []
            for match_number, match in enumerate(matches):
                # Split string at last comma before each period match.
                # This might yield a default period without dates, plus exceptions.
                if match_number == 0:
                    default_period_end_index = string.rfind(",", 0, match.start())
                    if default_period_end_index > -1:
                        # default period found before comma
                        strings.append(string[:default_period_end_index])
                        last_string_end = default_period_end_index
                    else:
                        # no comma found before date
                        last_string_end = -1
                if match_number < len(matches) - 1:
                    next_match_start = matches[match_number + 1].start()
                    splitting_index = string.rfind(",", match.end(), next_match_start)
                    if splitting_index == -1:
                        # No comma between periods, split before next period.
                        splitting_index = next_match_start
                    strings.append(string[last_string_end + 1 : splitting_index])
                    last_string_end = splitting_index - 1
                else:
                    # we reached the end of the string
                    strings.append(string[last_string_end + 1 :])
        # offset matches by one if default period string was encountered first
        if len(strings) > len(matches):
            matches.insert(0, None)

        for period_str, match in zip(strings, matches):
            # if we have no match, the default period starts today
            start_date = date.today()
            end_date = None
            if not match:
                # no dates known
                if "poikkeuksellisesti" in period_str:
                    override = True
                else:
                    override = False
                periods.append(
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "string": period_str,
                        "override": override,
                        "resource_state": State.UNDEFINED,
                    }
                )
            else:
                if match.group(2):
                    # two dates found, start and end!
                    start_date, end_date = self.parse_dates(
                        match.group(2), match.group(12)
                    )
                else:
                    if (match.group(1) and "alkaen" in match.group(1)) or (
                        match.group(19) and "alkaen" in match.group(19)
                    ):
                        # starting date known
                        start_date, end_date = self.parse_dates(match.group(12), None)
                    elif match.group(19) and "asti" in match.group(19):
                        # end date known
                        start_date, end_date = self.parse_dates(None, match.group(12))
                    else:
                        # single day exception
                        start_date, end_date = self.parse_dates(
                            match.group(12), match.group(12)
                        )
                if "poikkeuksellisesti" in period_str:
                    override = True
                else:
                    override = False
                if [
                    period
                    for period in periods
                    if period["start_date"] == start_date
                    and period["end_date"] == end_date
                ]:
                    self.logger.info(
                        "Cannot import another string with same dates: {0}".format(
                            period_str
                        )
                    )
                    continue
                periods.append(
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "override": override,
                        "string": period_str,
                        "resource_state": State.UNDEFINED,
                    }
                )
        return periods

    def parse_opening_string(self, string: str) -> list:
        """
        Takes TPREK simple Finnish opening hours string for a single period
        and returns corresponding opening time spans, if found.
        """
        time_spans = []
        # match to single datum, e.g. "ma-pe 8-16:30" or "suljettu pe" or
        # "joka päivä 07-" or "ma, ke, su klo 8-12, 16-20" or "8.12.2020 klo 8-16"
        # https://regex101.com/r/UkhZ4e/25
        pattern = re.compile(
            r"(\s(suljettu|kiinni|avoinna|auki)(\spoikkeuksellisesti)?|huoltotauko|\sja)?\s?("  # noqa
            + date_or_span_regex
            + r")?\s?-?\s?(\s"
            + multiple_weekday_spans_regex
            + r"|(\s"
            + date_or_span_regex
            + r")|joka päivä|päivittäin|avoinna|päivystys)(\s"
            + date_optional_month_regex
            + r")?(\s|\.|$)(ke?ll?o\s)*(suljettu|ympäri vuorokauden|24\s?h|"
            + multiple_time_spans_regex
            + r")?(\s(alkaen|asti))?",  # noqa
            re.IGNORECASE,
        )
        # 1) standardize formatting to get single whitespaces everywhere
        # 2) standardize dashes
        # 3) get rid of common typos:
        #   - "klo.", "klo:" -> "klo "
        string = " " + " ".join(string.split()).replace("−", "-")
        string = string.replace("klo.", "klo").replace("klo:", "klo")

        matches = pattern.finditer(string)

        for match in matches:
            # 1) Try to find weekday ranges
            weekdays = []
            start_weekday_indices = (25, 30, 35, 40)
            for start_index in start_weekday_indices:
                if match.group(start_index):
                    end_index = start_index + 2
                    start_weekday = self.weekday_by_abbr[
                        match.group(start_index).lower()
                    ]
                    if match.group(end_index):
                        end_weekday = self.weekday_by_abbr[
                            match.group(end_index).lower()
                        ]
                        weekdays.extend(list(range(start_weekday, end_weekday + 1)))
                    else:
                        weekdays.extend([start_weekday])
            if not weekdays:
                weekdays = None

            # 2) Try to find start or end times
            if weekdays and (
                (
                    match.group(2)
                    and ("suljettu" in match.group(2) or "kiinni" in match.group(2))
                )
                or (match.group(71) and "suljettu" in match.group(71))
            ):
                # only given weekdays closed
                start_time = None
                end_time = None
                resource_state = State.CLOSED
                full_day = True
            elif match.group(94) == "asti":
                start_time = datetime_time(hour=0, minute=0)
                end_time = self.parse_time(match.group(72))
                resource_state = State.OPEN
                full_day = False
            elif match.group(72) or match.group(78):
                # start or end time found!
                start_time = self.parse_time(match.group(72))
                if not start_time:
                    start_time = datetime_time(hour=0, minute=0)
                end_time = self.parse_time(match.group(78))
                if not end_time:
                    end_time = datetime_time(hour=0, minute=0)
                if match.group(1) and "huoltotauko" in match.group(1):
                    resource_state = State.CLOSED
                else:
                    resource_state = State.OPEN
                full_day = False
            elif match.group(71) and (
                "ympäri vuorokauden" in match.group(71)
                or "24 h" in match.group(71)
                or "24h" in match.group(71)
            ):
                # always open
                start_time = None
                end_time = None
                resource_state = State.OPEN
                full_day = True

            # 3) No times found. We must have weekdays *or* päivittäin
            else:
                if not weekdays and not (
                    "joka päivä" in match.group(24) or "päivittäin" in match.group(24)
                ):
                    # We might have dates, but we have no times or weekdays.
                    # Skip time spans and let the whole period status suffice.
                    continue
                # mark given weekdays open with no exact times
                start_time = None
                end_time = None
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

            if match.group(81):
                # we might have another time span on the same day, if we're really
                # unlucky
                start_time = self.parse_time(match.group(84))
                end_time = self.parse_time(match.group(90))
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
        resource = self.resource_cache.get(unit_id, None)
        if not resource:
            self.logger.info(
                "Error in data, resource with given unit_id not found! {0}".format(
                    unit_id
                )
            )
            return []
        period_string = data.get("name_fi", "")
        if not period_string:
            self.logger.info(
                "Error parsing data, Finnish opening hours not found! {0}".format(data)
            )
        try:
            periods = self.parse_period_string(period_string)
        except ValueError:
            self.logger.info(
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
                self.logger.info(
                    "Error parsing period, most likely delimiters are missing! "
                    + "{0}".format(period)
                )
                continue

            # also update the period resource_state based on the whole period string
            if (
                not time_spans
                or all([span["resource_state"] == State.CLOSED for span in time_spans])
            ) and "suljettu" in period["string"]:
                resource_state = State.CLOSED
            elif (
                "suljettu" not in period["string"]
                and (
                    all([span["weekdays"] is None for span in time_spans])
                    or "päivystys" in period["string"]
                )
                and (
                    "ympäri vuorokauden" in period["string"]
                    or "24 h" in period["string"]
                    or "24h" in period["string"]
                )
            ):
                resource_state = State.OPEN
            else:
                resource_state = State.UNDEFINED

            # weather permitting
            if "säävarau" in period["string"] or "salliessa" in period["string"]:
                for time_span in time_spans:
                    if time_span["resource_state"] == State.OPEN:
                        time_span["resource_state"] = State.WEATHER_PERMITTING
                if not time_spans:
                    resource_state = State.WEATHER_PERMITTING

            # with reservation
            elif (
                "sopimukse" in period["string"]
                or "tilaukse" in period["string"]
                or ("varau" in period["string"] and "ilman" not in period["string"])
            ):
                for time_span in time_spans:
                    if time_span["resource_state"] == State.OPEN:
                        time_span["resource_state"] = State.WITH_RESERVATION
                if not time_spans or all(
                    [
                        span["resource_state"] == State.WITH_RESERVATION
                        for span in time_spans
                    ]
                ):
                    resource_state = State.WITH_RESERVATION

            start_date = period.get("start_date", date.today())
            end_date = period.get("end_date", None)
            origin = {
                "data_source_id": self.data_source.id,
                "origin_id": "{0}-{1}-{2}".format(connection_id, start_date, end_date),
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
        return data

    def filter_opening_hours_data(self, data: list) -> list:
        """
        Takes connection data list and filters the connections that should be imported.

        We only wish to import opening hours, and only for objects that have no openings
        from other sources.
        """
        libraries = Resource.objects.filter(
            origins__data_source=self.kirjastot_data_source
        )
        return [
            connection
            for connection in data
            if connection["section_type"] == "OPENING_HOURS"
            and self.resource_cache.get(str(connection["unit_id"]), None)
            not in libraries
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
        # Base importer knows how to update resource ancestry when saving it.
        # Signal receivers are never needed when importing.
        self.disconnect_receivers()

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
            obj_list = self.api_get(api_object_type, params=api_params)
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
