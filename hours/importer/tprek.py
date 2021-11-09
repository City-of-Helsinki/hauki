import csv
import re
from calendar import day_abbr, different_locale, month_name
from datetime import date
from datetime import time as datetime_time
from itertools import zip_longest
from typing import Hashable, Tuple

import pytz
from django import db
from django.conf import settings
from django.db.models.signals import m2m_changed
from django_orghierarchy.models import Organization
from model_utils.models import SoftDeletableModel

from ..enums import ResourceType, State, Weekday
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
CONNECTION_TYPES_TO_IGNORE = {
    "OPENING_HOURS",
    "SOCIAL_MEDIA_LINK",
}
# here we list the tprek connection types that should *not* be parsed for opening hours
CONNECTION_TYPES_TO_SKIP_HOURS = {
    "ESERVICE_LINK",
    "HIGHLIGHT",
    "LINK",
    "OTHER_ADDRESS",
    "SOCIAL_MEDIA_LINK",
    "TOPICAL",
}

# here we list the tprek resource types that always have common hours and may be
# merged if the strings are identical
RESOURCE_TYPES_TO_MERGE = {ResourceType.ONLINE_SERVICE, ResourceType.CONTACT}

# https://regex101.com/r/HOIX1L/4
date_or_span_regex = r"(alkaen\s)?(([0-3]?[0-9])\.(((10|11|12|[0-9])(\.|\s)|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)?(\s)?-(\s)?)?(([0-3]?[0-9])\.((10|11|12|[0-9])(\.|\s)|(\s[a-ö]{,6}kuuta\s))([0-9]{4})?)(\salkaen|\sasti)?,?"  # noqa
date_optional_month_regex = (
    r"(alkaen\s)?([0-3])?[0-9]\.((10|11|12|[0-9])\.?([0-9]{4})?)?"  # noqa
)
multiple_weekday_spans_regex = r"(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su]))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?((,|\sja)?\s(ma|ti|ke|to|pe|la|su)(\s?-\s?(ma|ti|ke|to|pe|la|su))?)?"  # noqa
multiple_time_spans_regex = r"([0-2]?[0-9]((\.|:)[0-9][0-9])?)((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?(((,|\sja)?\s([0-2]?[0-9]((\.|:)[0-9][0-9])?))((\s)?-(\s)?([0-2]?[0-9]((\.|:)[0-9][0-9])?))?)?"  # noqa


@register_importer
class TPRekImporter(Importer):
    name = "tprek"

    def setup(self):
        self.URL_BASE = "https://www.hel.fi/palvelukarttaws/rest/v4/"
        # The urls below are only used for constructing extra links for each unit
        self.ADMIN_URL_BASE = (
            "https://asiointi.hel.fi/tprperhe/TPR/UI/ServicePoint/ServicePointEdit/"
        )
        self.CITIZEN_URL_BASE = "https://palvelukartta.hel.fi/fi/unit/"
        self.data_source, _ = DataSource.objects.get_or_create(
            id="tprek",
            defaults={"name": "Toimipisterekisteri"},
        )
        self.kirjastot_data_source, _ = DataSource.objects.get_or_create(
            id="kirkanta",
            defaults={"name": "kirjastot.fi"},
        )

        self.ignore_hours_list = set()
        with open("hours/importer/tprek_ignore_hours_list.csv") as ignore_file:
            csv_reader = csv.reader(ignore_file, delimiter=";")
            # do not read the first line
            next(csv_reader)
            for row in csv_reader:
                self.ignore_hours_list.add(row[0])

        # this maps the imported resource names to Hauki objects
        self.data_to_match = {
            "unit": Resource.objects.filter(
                origins__data_source=self.data_source, resource_type=ResourceType.UNIT
            )
            .distinct()
            .prefetch_related("origins"),
            "connection": Resource.objects.filter(
                origins__data_source=self.data_source,
                resource_type__in=set(CONNECTION_TYPE_MAPPING.values())
                | set((ResourceType.SUBSECTION,)),
            )
            .distinct()
            .prefetch_related("origins"),
            # these are the proper TPR unit opening hours:
            "opening_hours": DatePeriod.objects.filter(
                origins__data_source=self.data_source,
                origins__origin_id__startswith="opening-",
            )
            .exclude(origins__data_source=self.kirjastot_data_source)
            .distinct()
            .prefetch_related("origins"),
            #
            # The following objects are not imported if --parse-nothing is used, to
            # prevent creating any opening hours found in resource data.
            #
            # these are the hours that are hidden in TPR unit description strings.
            "unit_opening_hours": DatePeriod.objects.filter(
                origins__data_source=self.data_source,
                origins__origin_id__startswith="description-",
            )
            .exclude(origins__data_source=self.kirjastot_data_source)
            .distinct()
            .prefetch_related("origins"),
            # these are the hours that are hidden in TPR connection strings:
            "connection_opening_hours": DatePeriod.objects.filter(
                origins__data_source=self.data_source,
                resource__resource_type__in=set(CONNECTION_TYPE_MAPPING.values())
                | set((ResourceType.SUBSECTION,)),
            )
            .exclude(origins__data_source=self.kirjastot_data_source)
            .distinct()
            .prefetch_related("origins"),
            #
            # The following objects are only imported if --parse-extra is used, as
            # they will also create subsections that do not exist in TPR.
            #
            # these are the subsections with hours that are hidden in TPR unit strings:
            "unit_subsections": Resource.objects.filter(
                origins__data_source=self.data_source,
                origins__origin_id__startswith="description-",
            )
            .distinct()
            .prefetch_related("origins"),
            # these are the subsections with hours that are hidden in TPR opening hours
            # strings:
            "opening_hours_subsections": Resource.objects.filter(
                origins__data_source=self.data_source,
                origins__origin_id__startswith="opening-",
                resource_type=ResourceType.SERVICE_AT_UNIT,
            )
            .distinct()
            .prefetch_related("origins"),
        }
        with different_locale("fi_FI.utf-8"):
            self.month_by_name = {
                name.lower(): index + 1
                for index, name in enumerate(list(month_name)[1:])
            }
            self.weekday_by_abbr = {
                abbr.lower(): index + 1 for index, abbr in enumerate(list(day_abbr))
            }

    def get_mergable_data_id(self, data: dict) -> Hashable:
        if (
            data.get("resource_type", None)
            and data["resource_type"] in RESOURCE_TYPES_TO_MERGE
        ):
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

    def mark_non_public(self, obj: Resource) -> bool:
        obj.is_public = False
        obj.save()

    def check_non_public(self, obj: Resource) -> bool:
        return not obj.is_public

    def mark_deleted(self, obj: SoftDeletableModel) -> bool:
        # Only TPREK units will be marked non-public instead of deleted.
        # They might still lurk in TPREK and be needed non-publicly.
        if type(obj) == Resource and obj.resource_type == ResourceType.UNIT:
            return self.mark_non_public(obj)
        # TPREK does not have non-public connections. Connections and opening
        # hours will be deleted.
        return super().mark_deleted(obj)

    def check_deleted(self, obj: SoftDeletableModel) -> bool:
        if type(obj) == Resource and obj.resource_type == ResourceType.UNIT:
            return self.check_non_public(obj)
        return super().check_deleted(obj)

    def parse_dates(self, start: str, end: str) -> Tuple[date, date]:
        """
        Parses period start and end dates. If end is given, start string may be
        incomplete.
        """
        if end:
            try:
                day = int(end.split(".")[0])

                if any([name in end for name in self.month_by_name.keys()]):
                    # month name found
                    month = self.month_by_name[
                        [name for name in self.month_by_name.keys() if name in end][0]
                    ]
                else:
                    month = int(end.split(".")[1])

                try:
                    year = int(end[-4:])
                except ValueError:
                    # end did not contain year, assume next occurrence of date
                    today = date.today()
                    if today > date(year=today.year, month=month, day=day):
                        year = today.year + 1
                    else:
                        year = today.year

                end = date(year=year, month=month, day=day)
            except ValueError:
                self.logger.info("Invalid end date {0}".format(end))
                end = None
        if start:
            try:
                day = int(start.split(".")[0])

                try:
                    if any([name in start for name in self.month_by_name.keys()]):
                        # month name found
                        month = self.month_by_name[
                            [
                                name
                                for name in self.month_by_name.keys()
                                if name in start
                            ][0]
                        ]
                    else:
                        month = int(start.split(".")[1])
                except ValueError:
                    # start did not contain month
                    month = end.month

                try:
                    year = int(start[-4:])
                except ValueError:
                    # start did not contain year
                    if end and month <= end.month:
                        # only use end year if start month is before end month
                        year = end.year
                    else:
                        # end did not contain year either, assume last occurrence of
                        # date
                        today = date.today()
                        if today > date(year=today.year, month=month, day=day):
                            year = today.year
                        else:
                            year = today.year - 1

                start = date(year=year, month=month, day=day)
            except (ValueError, AttributeError):
                self.logger.info("Invalid start date {0}".format(start))
                start = None
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

    def clean_parsed_subsection_name(self, name: str) -> name:
        # The hours are for a new subsection, remove superfluous words
        while (
            name.endswith(" on")
            or name.endswith(" ovat")
            or name.endswith(" ja")
            or name.endswith(" olemme")
            or name.endswith(" (")
        ):
            name = name.rsplit(" ", 1)[0]
        return name

    def split_string_between_matches(
        self, string: str, matches: list, split_before_first=True, delimiter=","
    ) -> dict:
        """
        Takes a string and its containing regex matches. Splits the string at
        last delimiter before each match, and returns dict where keys are the
        string starting indices and values the partial strings.
        """
        strings = {}
        for match_number, match in enumerate(matches):
            # Split string at last comma before each pattern match.
            # This might yield a default string without match, plus any number
            # of strings corresponding to matches.
            if match_number == 0:
                last_comma_index = -1
                if split_before_first:
                    last_comma_index = string.rfind(delimiter, 0, match.start())
                    if last_comma_index > -1:
                        # default string found before comma
                        strings[last_comma_index + 1] = string[:last_comma_index]
            if match_number < len(matches) - 1:
                next_match_start = matches[match_number + 1].start()
                splitting_index = string.rfind(delimiter, match.end(), next_match_start)
                if splitting_index == -1:
                    # No comma between matches, split before next match.
                    splitting_index = next_match_start
                strings[last_comma_index + 1] = string[
                    last_comma_index + 1 : splitting_index
                ]
                last_comma_index = splitting_index
            else:
                # we reached the end of the string
                strings[last_comma_index + 1] = string[last_comma_index + 1 :]
        return strings

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
        # 6) replace "sekä" with "ja"
        string = string.replace("sekä", "ja")

        matches = list(pattern.finditer(string))

        # no matches => just use the whole string
        if not matches:
            strings = {0: string}
        # one or more matches => one or more date periods
        else:
            strings = self.split_string_between_matches(string, matches)
        # offset matches by one if default period string was encountered first
        if len(strings) > len(matches):
            matches.insert(0, None)

        for period_str, match in zip(strings.values(), matches):
            # if we have no match, the default period is forever
            start_date = None
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
                if (
                    "poikkeuksellisesti" in period_str
                    or (start_date and start_date == end_date)
                    or (
                        [
                            period
                            for period in periods
                            if (
                                start_date
                                and (
                                    not period["start_date"]
                                    or start_date > period["start_date"]
                                )
                                and end_date
                                and (
                                    not period["end_date"]
                                    or end_date < period["end_date"]
                                )
                            )
                        ]
                    )
                ):
                    # single day exception, or short period within longer period
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

    def parse_opening_string(self, opening_string: str) -> list:
        """
        Takes TPREK simple Finnish opening hours string for a single period
        and returns corresponding opening time spans, if found.

        The result may be a list of multiple time span lists, because
        some period strings contain hours for multiple objects all put in one.
        In such a case, the importer will create an extra subsection and
        period for each time span list after the first.
        """
        time_span_lists = [[]]
        # match to single datum, e.g. "ma-pe 8-16:30" or "suljettu pe" or
        # "joka päivä 07-" or "ma, ke, su klo 8-12, 16-20" or "8.12.2020 klo 8-16"
        # https://regex101.com/r/UkhZ4e/26
        pattern = re.compile(
            r"(\s(suljettu|kiinni|avoinna|auki)(\spoikkeuksellisesti)?|huoltotauko|\sja)?\s?("  # noqa
            + date_or_span_regex
            + r")?\s?-?\s?(\s"
            + multiple_weekday_spans_regex
            + r"|(\s"
            + date_or_span_regex
            + r")|joka päivä|päivittäin|arkisin|viikonloppuisin|avoinna|päivystys)(\s"
            + date_optional_month_regex
            + r")?(\s|\.|$)(ke?ll?o\s)*(suljettu|ympäri vuorokauden|24\s?h|"
            + multiple_time_spans_regex
            + r")?(\s(alkaen|asti))?",  # noqa
            re.IGNORECASE,
        )
        # 1) standardize formatting to get single whitespaces everywhere
        # 2) standardize dashes
        # 3) get rid of common typos:
        #   - "klo.", "klo:", "kl." -> "klo "
        string = " " + " ".join(opening_string.split()).replace("−", "-")
        string = (
            string.replace("klo.", "klo").replace("klo:", "klo").replace("kl.", "klo")
        )

        matches = list(pattern.finditer(string))

        # no matches => just use the whole string
        if not matches:
            strings = {0: string}
        # one or more matches => one or multiple time spans
        else:
            strings = self.split_string_between_matches(
                string, matches, split_before_first=False
            )

        subsection_number = 0
        names = []
        descriptions = []
        for match_number, (str_start, match) in enumerate(zip(strings, matches)):
            # 0) Remainder of the string may give period name and description
            if match_number == 0:
                # Save parts before first match
                # and after last match as period name and description
                name = string[: match.start()]
                names.append(name)
            elif str_start < match.start():
                # Found match might be for a new subsection!
                # This is indicated by an extra string after comma between matches
                subsection_number += 1
                time_span_lists.append([])
                name = string[str_start : match.start()]
                names.append(name)
                # Now we also know the description after the end of previous match
                descriptions.append(string[matches[match_number - 1].end() : str_start])
            if match_number == len(matches) - 1:
                # after the last match, what remains of the string is the last
                # description
                descriptions.append(string[match.end() :])

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
                        weekdays.extend(
                            list(
                                [
                                    Weekday.from_iso_weekday(weekday)
                                    for weekday in range(start_weekday, end_weekday + 1)
                                ]
                            )
                        )
                    else:
                        weekdays.extend([Weekday.from_iso_weekday(start_weekday)])
            if not weekdays:
                if "arkisin" in match.group(24):
                    weekdays = Weekday.business_days()
                elif "viikonloppuisin" in match.group(24):
                    weekdays = Weekday.weekend()
                else:
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
                start_time = None
                end_time = self.parse_time(match.group(72))
                resource_state = State.OPEN
                full_day = False
            elif match.group(94) == "alkaen":
                start_time = self.parse_time(match.group(72))
                end_time = None
                resource_state = State.OPEN
                full_day = False
            elif match.group(72) or match.group(78):
                # start or end time found!
                start_time = self.parse_time(match.group(72))
                end_time = self.parse_time(match.group(78))
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

            # 3) No times found.
            # We must have "avoinna" + weekdays *or* "avoinna" + "päivittäin".
            else:
                if not (
                    (match.group(2) and "avoinna" in match.group(2))
                    or (match.group(24) and "avoinna" in match.group(24))
                ) or (
                    not weekdays
                    and not (
                        "joka päivä" in match.group(24)
                        or "päivittäin" in match.group(24)
                    )
                ):
                    # No status or no days specified.
                    # Skip time spans and let the whole period status suffice.
                    continue
                # mark given or all weekdays open with no exact times
                start_time = None
                end_time = None
                resource_state = State.OPEN
                full_day = False

            end_time_on_next_day = False
            if start_time and end_time and end_time <= start_time:
                end_time_on_next_day = True

            time_spans = time_span_lists[subsection_number]
            time_spans.append(
                {
                    "group": None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "weekdays": weekdays,
                    "resource_state": resource_state,
                    "full_day": full_day,
                    "end_time_on_next_day": end_time_on_next_day,
                }
            )
            if match.group(81):
                # we might have another time span on the same day, if we're really
                # unlucky
                start_time = self.parse_time(match.group(84))
                end_time = self.parse_time(match.group(90))
                resource_state = State.OPEN
                full_day = False
                end_time_on_next_day = False
                if start_time and end_time and end_time <= start_time:
                    end_time_on_next_day = True
                time_spans.append(
                    {
                        "group": None,
                        "start_time": start_time,
                        "end_time": end_time,
                        "weekdays": weekdays,
                        "resource_state": resource_state,
                        "full_day": full_day,
                        "end_time_on_next_day": end_time_on_next_day,
                    }
                )

        names = [name.strip(" ,:;-").capitalize() for name in names]
        descriptions = [
            description.strip(" ,:;-.").capitalize() for description in descriptions
        ]
        return time_span_lists, names, descriptions

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

        origins = self.get_unit_origins(data)
        description = self.get_multilanguage_string("desc", data)

        periods = []
        subsections = []
        unit_id = self.get_data_ids({"origins": origins})[0]
        if (
            unit_id not in self.ignore_hours_list
            and not self.options.get("parse_nothing", False)
            and description["fi"]
        ):
            # unit description may itself contain opening hour strings to import.
            # however, they are only small parts of the whole string composed
            # of multiple sentences.
            initials_sentences_and_delimiters = re.split(
                r"(\.)([\n\r\s][A-ZÅÄÖ])", description["fi"]
            )
            initials_sentences_and_delimiters.insert(0, "")
            sentences = []
            for initial, sentence, delimiter in zip_longest(
                initials_sentences_and_delimiters[::3],
                initials_sentences_and_delimiters[1::3],
                initials_sentences_and_delimiters[2::3],
                fillvalue="",
            ):
                sentences.append(initial + sentence + delimiter)

            # construct period ids by referring to the originating field
            opening_hours_by_sentence = [
                self.get_opening_hours_data(
                    {
                        "unit_id": unit_id,
                        "name_fi": sentence,
                        "connection_id": "description-" + unit_id,
                    },
                    allow_missing_resource=True,
                )
                for sentence in sentences
            ]

            description["fi"] = ""
            for sentence, hours in zip(sentences, opening_hours_by_sentence):
                if hours:
                    # Sentence contained opening hour strings.
                    # Omit sentence from description
                    name = hours[0]["name"]["fi"]
                    if (
                        name.lower() == "aukioloajat"
                        or name.lower() == "aukiolojakso"
                        or name.lower() == "perusaukiolo"
                        or name.lower() == "poikkeusaukiolo"
                    ):
                        # The hours are for the unit itself
                        periods.extend(hours)
                    elif self.options.get("parse_extra", False):
                        # The hours are for a new subsection
                        hours[0]["name"]["fi"] = name
                        subsections.extend(hours)
                else:
                    # Concatenate sentences with no opening hours
                    description["fi"] += sentence

        unit_data = {
            "origins": origins,
            "resource_type": ResourceType.UNIT,
            "name": self.get_resource_name(data),
            "description": description,
            "address": self.get_unit_address(data),
            "same_as": self.get_url("unit", data["id"]),
            "organization": obj_organization,
            "extra_data": self.get_unit_links(data),
            "timezone": pytz.timezone("Europe/Helsinki"),
            "periods": periods,
            "subsections": subsections,
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
        connection_id = str(data.get("connection_id"))
        unit_id = str(data.get("unit_id"))
        origin = {
            "data_source_id": self.data_source.id,
            "origin_id": connection_id,
        }
        # parent may be missing if e.g. the unit has just been created or
        # deleted, or is not public at the moment. Therefore, parent may be empty.
        parent = self.resource_cache.get(unit_id, None)
        parents = [parent] if parent else []
        name = self.get_resource_name(data)
        description = self.get_connection_description(data)
        opening_hours = []

        if (
            connection_id not in self.ignore_hours_list
            and not self.options.get("parse_nothing", False)
            and data.get("section_type") not in CONNECTION_TYPES_TO_SKIP_HOURS
        ):
            # connection may also contain opening hour strings that we want to import
            opening_hours = self.get_opening_hours_data(
                data, allow_missing_resource=True
            )
            if opening_hours:
                # connection string contained opening hour strings, use strings
                # stripped of opening hours data instead.
                if "aukiolo" in opening_hours[0]["name"]["fi"].lower():
                    # String refers to period, no resource name found
                    name["fi"] = "Alikohde"
                else:
                    # String refers to resource, no period name found
                    name["fi"] = self.clean_parsed_subsection_name(
                        opening_hours[0]["name"]["fi"]
                    )
                    opening_hours[0]["name"]["fi"] = "Perusaukiolo"
                    opening_hours[0]["description"]["fi"] = ""

        # incoming data will be saved raw in extra_data, to allow matching identical
        # connections
        data.pop("connection_id", None)
        data.pop("unit_id", None)
        connection_data = {
            "origins": [origin],
            "resource_type": CONNECTION_TYPE_MAPPING[data["section_type"]],
            "name": name,
            "description": description,
            "address": self.get_resource_name(data)
            if CONNECTION_TYPE_MAPPING[data["section_type"]] == ResourceType.ENTRANCE
            else "",
            "parents": parents,
            "extra_data": data,
            "periods": opening_hours,
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

    def get_opening_hours_data(self, data: dict, allow_missing_resource=False) -> list:
        """
        Takes connection data dict in TPREK v4 API format and returns the corresponding
        serialized DatePeriods.
        """
        unit_id = str(data.pop("unit_id"))
        if "connection_id" not in data:
            # opening hours do not have id in TPREK API, generate id from unit id
            data["connection_id"] = "opening-" + unit_id
        connection_id = str(data.pop("connection_id"))

        if data.get("section_type", None) in CONNECTION_TYPE_MAPPING:
            # In case we are importing hours in non-opening hours connection, add hours
            # to the original connection instead, not the unit directly
            resource_id = connection_id
        else:
            # the opening hours refer to unit directly
            resource_id = unit_id
        if resource_id in self.ignore_hours_list:
            return []

        resource = self.resource_cache.get(resource_id, None)
        # Resource may be missing if the resource is being created by the same importer
        # or has been recently deleted or added.
        if not resource and not allow_missing_resource:
            self.logger.info(
                "Cannot import hours yet, resource with given id not found! {0}".format(
                    resource_id
                )
            )
            return []
        period_string = data.get("name_fi", "")
        if not period_string:
            self.logger.info(
                "Error parsing data, Finnish opening hours not found! {0}".format(data)
            )
            return []
        periods = self.parse_period_string(period_string)

        data = []
        for period in periods:
            parsed_time_spans, names, descriptions = self.parse_opening_string(
                period["string"]
            )
            # Time spans may be grouped if several different services are found!
            # In this case, each additional group will give rise to an additional
            # period in an additional subsection, even though only one period string
            # was originally found.

            for time_spans, name, description in zip(
                parsed_time_spans, names, descriptions
            ):
                # finally update whole period resource_state based on timespans and
                # string
                if (
                    not time_spans
                    # only mark period closed if *all* spans are closed
                    or all(
                        [span["resource_state"] == State.CLOSED for span in time_spans]
                    )
                ) and (
                    "suljettu" in period["string"] or "suljetaan" in period["string"]
                ):
                    # "suljettu" found
                    resource_state = State.CLOSED
                elif (
                    # closed not found, looking for open
                    ("avoinna" in period["string"] or "päivystys" in period["string"])
                    and (
                        not time_spans
                        # only mark period open if *all* weekdays are open
                        or all(
                            [
                                (
                                    not span["weekdays"]
                                    or span["weekdays"] == set(range(1, 7))
                                )
                                and (span["resource_state"] == State.OPEN)
                                for span in time_spans
                            ]
                        )
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

                # Use some generic strings if period got no name
                if not name and "päivystys" in period["string"]:
                    name = "Päivystys"

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
                    or "vuokrau" in period["string"]
                    or "ennalta" in period["string"]
                    or "ennakkoon" in period["string"]
                    or "varauksella" in period["string"]
                    or "varauksesta" in period["string"]
                    or "varausten" in period["string"]
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

                # with key
                elif "avai" in period["string"]:
                    for time_span in time_spans:
                        if time_span["resource_state"] == State.OPEN:
                            time_span["resource_state"] = State.WITH_KEY
                    if not time_spans or all(
                        [
                            span["resource_state"] == State.WITH_KEY
                            for span in time_spans
                        ]
                    ):
                        resource_state = State.WITH_KEY

                start_date = period.get("start_date", date.today())
                end_date = period.get("end_date", None)
                origin = {
                    "data_source_id": self.data_source.id,
                    "origin_id": "{0}-{1}-{2}".format(
                        connection_id, start_date, end_date
                    ),
                }
                if time_spans:
                    time_span_groups = [
                        {
                            "time_spans": time_spans,
                            "rules": [],
                        }
                    ]
                else:
                    time_span_groups = []

                # Period might have no time spans. In this case, if also period state
                # is undefined, it contains no data and should not be saved.
                if not time_span_groups and resource_state == State.UNDEFINED:
                    continue

                # Often data does not contain name. Use certain default strings
                # based on period status
                if not name:
                    if not start_date or not end_date:
                        name = "Perusaukiolo"
                    else:
                        name = "Aukiolojakso"
                    if period["override"]:
                        name = "Poikkeusaukiolo"

                period_datum = {
                    "resource": resource,
                    "name": {"fi": name[:255]},
                    "description": {"fi": description},
                    "start_date": start_date,
                    "end_date": end_date,
                    "override": period["override"],
                    "resource_state": resource_state,
                    "origins": [origin],
                    "time_span_groups": time_span_groups,
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
        Imports objects of the given type. Uses get_data_id to match incoming data with
        existing objects and get_mergable_data_id to check if objects should be merged
        into a single object.
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
            data_source=self.data_source,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )
        obj_list = getattr(self, "filter_%s_data" % object_type)(obj_list)
        self.logger.info("%s %ss loaded" % (len(obj_list), object_type))
        obj_dict = {}
        extra_subsections = {}
        extra_periods = {}
        for idx, data in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss read" % (idx, object_type))
            object_data = getattr(self, "get_%s_data" % object_type)(data)
            if not isinstance(object_data, list):
                # wrap single objects in list, because object_data may also contain
                # multiple objects
                object_data = [object_data]
            for datum in object_data:
                object_data_id = (
                    self.get_mergable_data_id(datum)
                    if self.options["merge"]
                    else self.get_data_ids(datum)[0]
                )
                if object_data_id not in obj_dict:
                    obj_dict[object_data_id] = datum
                    # Some resources have their opening periods in resource string
                    if datum.get("periods", None):
                        extra_periods[self.get_data_ids(datum)[0]] = datum["periods"]
                else:
                    # We are trying to import an object whose id has already been
                    # imported. How to handle it depends on object type.
                    if object_type == "opening_hours":
                        # Create new subsections from duplicate opening periods
                        # that shouldn't be there in the first place.
                        self.logger.info(
                            f"Duplicate period {datum} found for same dates, period"
                            f" {obj_dict[object_data_id]} read already. Saving this"
                            f" as a new subsection if --parse-extra is used."
                        )
                        if (
                            self.get_object_ids(datum["resource"])[0]
                            in extra_subsections
                        ):
                            extra_subsections[
                                self.get_object_ids(datum["resource"])[0]
                            ].append(datum)
                        else:
                            extra_subsections[
                                self.get_object_ids(datum["resource"])[0]
                            ] = [datum]
                    if object_type == "connection":
                        # Duplicate connection found. Just append its foreign keys
                        # to merge connections instead of adding new object.
                        parents = datum["parents"]
                        origins = datum["origins"]
                        self.logger.info(
                            "Adding duplicate parent %s and origin %s to object %s"
                            % (parents, origins, object_data_id)
                        )
                        obj_dict[object_data_id]["parents"].extend(parents)
                        obj_dict[object_data_id]["origins"].extend(origins)
                # TODO: AFTER origins have been updated, we should compare changes. i.e.
                # - puhelinnumero jakautuu osiin => kaikille osille sama aukiolo
                # - puhelinnumeroita yhdistetään => suurimman massan aukiolo

                # Some resources have subsections and
                # their opening periods in resource string itself
                if datum.get("subsections", None):
                    extra_subsections[self.get_data_ids(datum)[0]] = datum[
                        "subsections"
                    ]
        for idx, object_data in enumerate(obj_dict.values()):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s %ss saved" % (idx, object_type))
            obj = getattr(self, f"save_{klass_str}")(object_data)

            syncher.mark(obj)

        # at the end, save any found additional periods. if parsing new subsections
        # is enabled, also extra subsections with periods will be saved.
        if not self.options.get("parse_nothing", False):
            period_syncher = (
                syncher
                if object_type == "opening_hours"
                else ModelSyncher(
                    self.data_to_match[object_type + "_opening_hours"],
                    data_source=self.data_source,
                    delete_func=self.mark_deleted,
                    check_deleted_func=self.check_deleted,
                )
            )
            self.save_extra_periods(period_syncher, extra_periods)
            if self.options.get("parse_extra", False):
                queryset = self.data_to_match.get(object_type + "_subsections", None)
                self.save_extra_subsections_with_periods(
                    period_syncher, extra_subsections, queryset
                )
            if not object_type == "opening_hours":
                # allow always deleting additional periods
                period_syncher.finish(force=True)
        syncher.finish(force=self.options["force"])

        self.reconnect_receivers()

    def save_extra_periods(self, period_syncher: ModelSyncher, extra_periods: dict):
        """
        Saves extra date periods that were found in resource strings.
        """
        if not extra_periods:
            return
        for resource_id, period_list in extra_periods.items():
            for datum in period_list:
                # datum may be missing its resource if it was just created
                datum["resource"] = self.resource_cache.get(resource_id, None)
                period = self.save_dateperiod(datum)
                period_syncher.mark(period)
        self.logger.info("Extra opening hours found in imported strings saved")

    def save_extra_subsections_with_periods(
        self, period_syncher: ModelSyncher, extra_subsections: list, data_to_match: str
    ):
        """
        Saves extra data found in opening hours, connection or unit
        strings as additional subsections, along with their opening hours.
        """
        if not extra_subsections:
            return
        subsection_syncher = ModelSyncher(
            data_to_match,
            data_source=self.data_source,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )

        obj_dict = {}
        for parent_id, subsection_list in extra_subsections.items():
            for datum in subsection_list:
                parent = self.resource_cache.get(parent_id, None)
                name = datum["name"]
                name["fi"] = self.clean_parsed_subsection_name(name["fi"])
                # We have no way of knowing what the subsection type should be.
                # Use a different type so generated subsections won't be mixed
                # with other ones.
                subsection_data = {
                    "origins": datum["origins"],
                    "resource_type": ResourceType.SERVICE_AT_UNIT,
                    "name": name
                    if not (
                        name["fi"] == "Aukioloajat"
                        or name["fi"] == "Aukiolojakso"
                        or name["fi"] == "Perusaukiolo"
                        or name["fi"] == "Poikkeusaukiolo"
                    )
                    else {"fi": "Alikohde"},
                    "description": datum["description"],
                    "parents": [parent],
                }
                data_id = subsection_data["origins"][0]["origin_id"]

                # if we had several duplicate periods, use running index in id
                idx = 0
                while data_id in obj_dict:
                    idx += 1
                    data_id = (
                        subsection_data["origins"][0]["origin_id"] + "-" + str(idx)
                    )
                subsection_data["origins"][0]["origin_id"] = data_id
                obj_dict[data_id] = datum
                subsection = self.save_resource(subsection_data)
                subsection_syncher.mark(subsection)

                # get rid of data that is in subsection already
                del datum["resource"]
                del datum["name"]
                del datum["description"]

                # period id already used, add new subsection id to create period id
                datum["resource"] = subsection
                datum["origins"][0]["origin_id"] = "opening-" + data_id
                datum["name"] = {"fi": "Perusaukiolo"}
                period = self.save_dateperiod(datum)
                period_syncher.mark(period)
        # allow always deleting extra subsections
        subsection_syncher.finish(force=True)
        self.logger.info("Extra subsections and opening hours found in strings saved")

    @db.transaction.atomic
    def import_units(self):
        self.logger.info("Importing TPREK units")
        self.import_objects("unit")

    @db.transaction.atomic
    def import_connections(self):
        self.logger.info("Importing TPREK connections")
        if self.options.get("merge", None):
            self.logger.info("Merging mergeable connections")
        self.import_objects("connection")

    def import_resources(self):
        self.import_units()
        self.import_connections()

    def import_openings(self):
        self.logger.info("Importing TPREK opening hours")
        self.import_objects("opening_hours")
