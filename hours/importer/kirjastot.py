import typing
from collections import defaultdict
from datetime import date, datetime, time
from itertools import groupby
from operator import itemgetter
from typing import TypedDict

import holidays
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django import db
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from requests import RequestException

from ..enums import RuleContext, RuleSubject, State, Weekday
from ..models import (
    DataSource,
    DatePeriod,
    Resource,
    TimeElement,
    combine_element_time_spans,
    get_daily_opening_hours_for_date_periods,
)
from ..signals import DeferUpdatingDenormalizedDatePeriodData
from .base import Importer, register_importer
from .sync import ModelSyncher

KIRKANTA_STATUS_MAP = {0: State.CLOSED, 1: State.OPEN, 2: State.SELF_SERVICE}
fi_holidays = holidays.Finland()

# List of periods that are known not to be a rotation of x weeks, but need to be
# handled day-by-day.
KIRKANTA_LONG_EXCEPTIONAL_PERIODS = [
    # Library "Metropolian kirjasto | Myyrmäki" Period "Joulu ja vuodenvaihde 2020"
    346087,
]

# Periods that are not usable from the kirkanta and are thus hard coded
KIRKANTA_FIXED_GROUPS = {
    # Library "Saksalainen kirjasto Deutsche Bibliothek" Period "Kirjaston aukioloajat"
    # Opening hours from their website:
    # https://www.deutsche-bibliothek.org/fi/kirjaston/oeffnungszeiten.html
    # maanantaisin klo 10-18, tiistai-perjantai klo 10-16
    # sekä kuukauden viimeisenä lauantaina klo 10-15.
    303888: [
        {
            "time_spans": [
                {
                    "group": None,
                    "start_time": time(hour=10, minute=0),
                    "end_time": time(hour=18, minute=0),
                    "weekdays": [Weekday.MONDAY],
                    "resource_state": State.OPEN,
                    "full_day": False,
                },
                {
                    "group": None,
                    "start_time": time(hour=10, minute=0),
                    "end_time": time(hour=16, minute=0),
                    "weekdays": [
                        Weekday.TUESDAY,
                        Weekday.WEDNESDAY,
                        Weekday.THURSDAY,
                        Weekday.FRIDAY,
                    ],
                    "resource_state": State.OPEN,
                    "full_day": False,
                },
            ],
            "rules": [],
        },
        {
            "time_spans": [
                {
                    "group": None,
                    "start_time": time(hour=10, minute=0),
                    "end_time": time(hour=15, minute=0),
                    "weekdays": [Weekday.SATURDAY],
                    "resource_state": State.OPEN,
                    "full_day": False,
                }
            ],
            "rules": [
                {
                    "group": None,
                    "context": RuleContext.MONTH,
                    "subject": RuleSubject.SATURDAY,
                    "start": -1,
                }
            ],
        },
    ],
}


class KirkantaPeriod(TypedDict):
    id: int
    library: int
    name: str
    validFrom: str
    validUntil: str
    isException: bool


class AnnotatedKirkantaPeriod(KirkantaPeriod):
    date: date
    index: int  # index in the original data
    weekday: int  # ISO 8601 weekday
    days: list[dict]  # annotated days for the period


class KirkakantaRefs(TypedDict):
    period: dict[str, KirkantaPeriod]


class KirkantaSchedule(TypedDict):
    date: str  # ISO 8601 date
    period: int  # period id, references KirkantaPeriod
    closed: bool
    times: list[dict]


class KirkantaData(TypedDict):
    schedules: list[KirkantaSchedule]


class KirkantaJsonResponse(TypedDict):
    type: str
    refs: KirkakantaRefs
    data: KirkantaData
    total: int


class KirjastotException(Exception):
    pass


class KirjastotImporterException(KirjastotException):
    pass


class KirjastotValidationError(KirjastotException):
    def __init__(self, msg: str = "", errors=None):
        self.msg = msg
        self.errors = errors or []

    def __str__(self):
        return self.msg


@register_importer
class KirjastotImporter(Importer):
    name = "kirjastot"

    def __init__(self, *args, **kwargs):
        self._errors = []
        self.URL_BASE = "https://api.kirjastot.fi/v4/"
        ds_args = dict(id="kirkanta")
        defaults = dict(name="kirjastot.fi")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_date_range(
        start: date = None, back: int = 1, forward: int = 12
    ) -> (date, date):
        """
        Returns a date range of "back" months before and "forward" months after
        given date, or today.
        """
        if not start:
            start = timezone.now().date()

        begin = start - relativedelta(months=back)
        end = start + relativedelta(months=forward)

        return begin, end

    def get_hours_from_api(
        self, resource: Resource, start: date, end: date
    ) -> KirkantaJsonResponse:
        """
        Fetch opening hours for Target from kirjastot.fi's v4 API for the
        given date range.
        """
        kirkanta_id = resource.origins.get(data_source=self.data_source).origin_id

        params = {
            "with": "schedules",
            "refs": "period",
            "period.start": start,
            "period.end": end,
        }
        try:
            data = self.api_get("library", kirkanta_id, params)
            if data["total"] > 0:
                return data
        except RequestException as e:
            self.logger.warning(
                "Could not fetch data from the kirjastot.fi API"
                " for library {}:{}. Error: {}".format(
                    self.data_source.id, kirkanta_id, str(e)
                )
            )

        return {}

    def check_period_common_dates_equal(
        self, period_id: int, first_data: list, second_data: list
    ) -> bool:
        """
        Checks that existing openings in both lists are equal, if their period_ids
        match.
        """
        if not first_data or not second_data:
            return True
        for first_opening, second_opening in zip(first_data, second_data):
            if not first_opening or not second_opening:
                # either pattern has no data for the given day, so it's always a match
                # for the day
                continue
            # times are not necessarily in the same order. order the times with status
            # and start first
            first_opening["times"].sort(key=itemgetter("status", "from", "to"))
            second_opening["times"].sort(key=itemgetter("status", "from", "to"))
            if (
                first_opening["period"] == period_id
                and second_opening["period"] == period_id
                and first_opening["times"] != second_opening["times"]
            ):
                return False
        return True

    def get_weekday_pattern_candidate(
        self, weekday_openings_by_date: list, n: int, period_id: int
    ) -> list:
        """
        Returns the pattern for n consecutive weeks from weekday_openings_by_date,
        merging data from several repetitions to find all n weeks with period_id.
        """
        first_n_weeks = weekday_openings_by_date[0:n]
        weeks_to_return = []
        for index, weekly_opening in enumerate(first_n_weeks):
            try:
                round = 0
                while weekly_opening["period"] != period_id:
                    # this opening won't do, looking at the next repetition
                    round += 1
                    weekly_opening = weekday_openings_by_date[round * n + index]
            except IndexError:
                # period doesn't contain a single opening for this weekday
                weekly_opening = None
            weeks_to_return.append(weekly_opening)
        return weeks_to_return

    def get_openings(self, data: list, period_start: date = None) -> list:
        """
        Generates serialized opening rules for a single period from sorted list of
        dates and their opening times. Each period needs to be processed separately.
        Dates may not be missing, but their data may be missing.

        We assume missing data at start, end or middle is indication of period overlap
        and date filtering, not period irregularity, and extrapolate from all the data
        we have up to the period length.

        period_start must be specified if the period doesn't start from the first day
        of data. This is because weekly rotations are always counted from the start
        of the period. Otherwise period is assumed to start on first date of data.
        """
        period_id = data[0]["period"]
        start_date = data[0]["date"]
        # starting date is needed to identify the first week, in case of repetitions of
        # multiple weeks
        if not period_start:
            period_start = start_date
        start_weekday = start_date.isoweekday()
        period_start_weekday = period_start.isoweekday()
        openings_by_weekday = groupby(
            sorted(data, key=itemgetter("weekday")), key=itemgetter("weekday")
        )

        # 1st (preprocess): group by differing times for the same weekday, if found,
        # and find the repetitions
        repetition_pattern = {}
        for weekday, openings_by_date in openings_by_weekday:
            openings_by_date = list(openings_by_date)
            n_weeks = len(openings_by_date)
            pattern_candidate = []
            # starting from the assumption that the openings repeat weekly, we increase
            # the repetition by one week and try again until the pattern matches
            for repetition in range(1, n_weeks + 1):
                pattern_candidate = self.get_weekday_pattern_candidate(
                    openings_by_date, repetition, period_id
                )
                slices = [
                    openings_by_date[i : i + repetition]
                    for i in range(0, n_weeks, repetition)
                ]
                # *all* slices must be equal whenever the period_id matches
                for pattern_slice in slices:
                    if not self.check_period_common_dates_equal(
                        period_id, pattern_slice, pattern_candidate
                    ):
                        # slice mismatch, no repetition
                        break
                else:
                    # end of loop reached, hooray! We have the repetition
                    break
            repetition_pattern[weekday] = pattern_candidate

        # first week may be partial, so openings for some weekdays start from the second
        # week, first week pattern is found at the end. move those patterns by one week
        for weekday, pattern in repetition_pattern.items():
            if weekday < start_weekday:
                repetition_pattern[weekday] = [pattern[-1]] + pattern[:-1]

        # repetition pattern may actually start in the middle of the period if we don't
        # have data from period start. shift the pattern so it starts from period start
        days_to_shift = (
            start_date
            - relativedelta(days=start_weekday - 1)
            - period_start
            + relativedelta(days=period_start_weekday - 1)
        )
        weeks_to_shift = days_to_shift.weeks
        for weekday, pattern in repetition_pattern.items():
            repetition_length = len(pattern)
            slice_index = weeks_to_shift % repetition_length
            if slice_index:
                repetition_pattern[weekday] = (
                    pattern[-slice_index:] + pattern[: repetition_length - slice_index]
                )

        # 2nd (loop again): generate time span groups based on the data for each
        # weekday and varying repetition length
        openings_by_repetition_length = groupby(
            sorted(repetition_pattern.values(), key=len), len
        )
        time_span_groups = []
        for length, patterns in openings_by_repetition_length:
            openings_by_week = zip(*patterns)
            for rotation_week_num, week_opening_times in enumerate(openings_by_week):
                week_opening_times_by_status = defaultdict(list)
                for day_in_the_week in week_opening_times:
                    # Opening times may be empty if we have no data for this
                    # particular day of the period
                    if day_in_the_week:
                        if day_in_the_week["times"]:
                            for week_opening_time in day_in_the_week["times"]:
                                week_opening_time["weekday"] = day_in_the_week[
                                    "weekday"
                                ]
                                week_opening_times_by_status[
                                    week_opening_time["status"]
                                ].append(week_opening_time)
                        else:
                            # Closed for the whole day
                            week_opening_times_by_status[0].append(
                                {"weekday": day_in_the_week["weekday"]}
                            )
                time_spans = []
                for status, week_opening_times in week_opening_times_by_status.items():
                    for week_opening_time in week_opening_times:
                        if "from" not in week_opening_time:
                            week_opening_time["from"] = ""
                        if "to" not in week_opening_time:
                            week_opening_time["to"] = ""

                    grouped_times = groupby(
                        sorted(week_opening_times, key=itemgetter("from", "to")),
                        itemgetter("from", "to"),
                    )
                    for opening_time, opening_times in grouped_times:
                        full_day = False
                        end_time_on_next_day = False
                        start_time = (
                            datetime.strptime(opening_time[0], "%H:%M").time()
                            if opening_time[0]
                            else None
                        )
                        end_time = (
                            datetime.strptime(opening_time[1], "%H:%M").time()
                            if opening_time[1]
                            else None
                        )
                        if not start_time and not end_time:
                            full_day = True
                        if start_time and end_time:
                            if end_time < start_time or (
                                start_time == time(hour=0, minute=0)
                                and end_time == time(hour=0, minute=0)
                            ):
                                end_time_on_next_day = True

                        time_spans.append(
                            {
                                "group": None,
                                "start_time": start_time,
                                "end_time": end_time,
                                "end_time_on_next_day": end_time_on_next_day,
                                "weekdays": [
                                    Weekday.from_iso_weekday(i["weekday"])
                                    for i in opening_times
                                ],
                                "resource_state": KIRKANTA_STATUS_MAP[status],
                                "full_day": full_day,
                            }
                        )
                time_span_group = {
                    "time_spans": time_spans,
                    "rules": [],
                }
                if length > 1:
                    time_span_group["rules"].append(
                        {
                            "group": None,
                            "context": RuleContext.PERIOD,
                            "subject": RuleSubject.WEEK,
                            "start": rotation_week_num + 1,
                            "frequency_ordinal": length,
                        }
                    )
                time_span_groups.append(time_span_group)

        return time_span_groups

    def separate_exceptional_periods(self, resource: Resource, period: dict) -> list:
        if all([d.get("closed", True) for d in period["days"]]):
            return [
                {
                    "resource": resource,
                    "name": {"fi": period.get("name", "")},
                    "start_date": parse(period["validFrom"]).date(),
                    "end_date": parse(period["validUntil"]).date(),
                    "resource_state": State.CLOSED,
                    "override": True,
                    "origins": [
                        {
                            "data_source_id": self.data_source.id,
                            "origin_id": str(period["id"]),
                        }
                    ],
                }
            ]

        periods = []
        for day in period["days"]:
            name = day.get("info") if day.get("info") else fi_holidays.get(day["date"])
            sub_period = {
                "resource": resource,
                "name": {"fi": name},
                "start_date": day["date"],
                "end_date": day["date"],
                "resource_state": State.UNDEFINED,
                "override": True,
                "origins": [
                    {
                        "data_source_id": self.data_source.id,
                        "origin_id": str(period["id"]) + "-" + str(day["date"]),
                    }
                ],
            }
            if day["closed"]:
                sub_period["resource_state"] = State.CLOSED
                periods.append(sub_period)
                continue

            time_spans = []
            for opening_time in day["times"]:
                full_day = False
                end_time_on_next_day = False
                start_time = (
                    datetime.strptime(opening_time["from"], "%H:%M").time()
                    if opening_time["from"]
                    else None
                )
                end_time = (
                    datetime.strptime(opening_time["to"], "%H:%M").time()
                    if opening_time["to"]
                    else None
                )
                if not start_time and not end_time:
                    full_day = True
                if start_time and end_time:
                    if end_time < start_time or (
                        start_time == time(hour=0, minute=0)
                        and end_time == time(hour=0, minute=0)
                    ):
                        end_time_on_next_day = True

                time_spans.append(
                    {
                        "group": None,
                        "start_time": start_time,
                        "end_time": end_time,
                        "end_time_on_next_day": end_time_on_next_day,
                        "resource_state": KIRKANTA_STATUS_MAP[opening_time["status"]],
                        "name": {"fi": day.get("info")},
                        "full_day": full_day,
                    }
                )
            sub_period["time_span_groups"] = [
                {
                    "time_spans": time_spans,
                    "rules": [],
                }
            ]
            periods.append(sub_period)

        return periods

    def get_kirkanta_periods(
        self, data: KirkantaJsonResponse
    ) -> dict[str, AnnotatedKirkantaPeriod]:
        """
        Annotates kirkanta data so that periods contain indexed data for each day for
        their duration. Returned periods may contain empty days or days belonging to
        other periods, since original data may have period overlaps.
        """
        periods = typing.cast(
            dict[str, AnnotatedKirkantaPeriod], data.get("refs", {}).get("period", None)
        )
        if not periods:
            return {}

        # sort the data just in case the API didn't
        data["data"]["schedules"].sort(key=lambda x: x["date"])
        # TODO: check for missing dates?

        # parse and annotate the data with day indices and weekdays
        for index, day in enumerate(data["data"]["schedules"]):
            day["date"] = parse(day["date"]).date()
            day["weekday"] = day["date"].isoweekday()
            day["index"] = index
        days_by_period = groupby(
            sorted(data["data"]["schedules"], key=itemgetter("period")),
            key=itemgetter("period"),
        )
        for period_id, days in days_by_period:
            days = list(days)
            start_index = days[0]["index"]
            end_index = days[-1]["index"]
            # Here we just slice the data for the duration of the period.
            # All days must be present for rotation indexing.
            schedules = data["data"]["schedules"][start_index : end_index + 1]
            period_id_string = str(period_id)
            if period_id_string not in periods.keys():
                self.logger.info(
                    "Period {} not found in periods! Ignoring data {}".format(
                        period_id_string, days
                    )
                )
            periods[period_id_string]["days"] = schedules

        return periods

    def _get_times_for_sort(self, item: TimeElement) -> tuple:
        return (
            item.start_time if item.start_time else "",
            item.end_time if item.end_time else "",
            # Resource state is included to sort items with the same start
            # and end times. Can't use Enum so we use the value instead.
            # The order of the states is not important here.
            item.resource_state.value if item.resource_state else "",
        )

    def _schedule_to_time_elements(
        self, schedule: KirkantaSchedule, override: bool
    ) -> list[TimeElement]:
        if schedule.get("closed") is True:
            return [
                TimeElement(
                    start_time=None,
                    end_time=None,
                    end_time_on_next_day=False,
                    resource_state=State.CLOSED,
                    override=override,
                    full_day=True,
                )
            ]

        time_elements = []
        for schedule_time in schedule.get("times"):
            try:
                start_time = datetime.strptime(
                    schedule_time.get("from"), "%H:%M"
                ).time()
            except ValueError:
                start_time = None
            try:
                end_time = datetime.strptime(schedule_time.get("to"), "%H:%M").time()
            except ValueError:
                end_time = None

            end_time_on_next_day = False
            if start_time and end_time:
                if end_time < start_time or (
                    start_time == time(hour=0, minute=0)
                    and end_time == time(hour=0, minute=0)
                ):
                    end_time_on_next_day = True

            time_elements.append(
                TimeElement(
                    start_time=start_time,
                    end_time=end_time,
                    end_time_on_next_day=end_time_on_next_day,
                    resource_state=KIRKANTA_STATUS_MAP[schedule_time["status"]],
                    override=override,
                    full_day=False,
                )
            )

        return time_elements

    @staticmethod
    def _get_override_periods_from_kirkanta_data(
        kirkanta_periods: dict[str, KirkantaPeriod], schedules: list[KirkantaSchedule]
    ) -> list[int]:
        """
        Returns a list of Kirkanta period ids that should override other date periods.
        """
        override_periods = []

        for kirkanta_period in kirkanta_periods.values():
            # If it's an exception, it's an override
            if kirkanta_period["isException"]:
                override_periods.append(kirkanta_period["id"])
                continue

            if kirkanta_period["validFrom"] and kirkanta_period["validUntil"]:
                valid_from = parse(kirkanta_period["validFrom"]).date()
                valid_until = parse(kirkanta_period["validUntil"]).date()
                # If the period is shorter than a week, it's an exception
                period_duration = valid_until - valid_from
                if period_duration.days < 7:
                    override_periods.append(kirkanta_period["id"])
                    continue

            # Find all schedules for this period
            period_schedules = [
                i for i in schedules if i.get("period") == kirkanta_period["id"]
            ]

            # If all days are closed, it's an override
            if all([d["closed"] for d in period_schedules]):
                override_periods.append(kirkanta_period["id"])

        return override_periods

    def check_library_data(
        self,
        library: Resource,
        periods: list[DatePeriod],
        data: KirkantaJsonResponse,
        start_date,
        end_date,
        has_fixed_periods: bool,
        raise_exception: bool = True,
    ) -> bool:
        """Checks that the daily opening hours from database match the schedule from Kirkanta.
        Raises KirjastotValidationError if they don't match"""
        if has_fixed_periods:
            self.logger.info("Library has fixed periods, skipping.")
            return True

        schedules = data.get("data", {}).get("schedules")

        if not schedules:
            self.logger.info("No schedules found in the incoming data. Skipping.")
            return True

        errors = []
        override_periods = self._get_override_periods_from_kirkanta_data(
            data.get("refs", {}).get("period", {}), schedules
        )
        opening_hours = get_daily_opening_hours_for_date_periods(
            periods, start_date, end_date
        )
        is_ok = True

        for schedule in schedules:
            override = schedule.get("period") in override_periods
            schedule_date = schedule.get("date")
            if not isinstance(schedule_date, date):
                schedule_date = parse(schedule.get("date")).date()

            # Opening hours from Kirkanta
            expected_time_elements = self._schedule_to_time_elements(schedule, override)
            expected_time_elements = combine_element_time_spans(
                expected_time_elements, override=override
            )
            expected_time_elements.sort(key=self._get_times_for_sort)

            # Actual opening hours currently in the database
            current_date_opening_hours = sorted(
                opening_hours[schedule_date], key=self._get_times_for_sort
            )

            if expected_time_elements != current_date_opening_hours:
                self.logger.warning(
                    f"Opening hours do not match between Kirkanta and the database\n"
                    f"Expected (Kirkanta): {expected_time_elements}\n"
                    f"Got (database): {current_date_opening_hours}\n",
                )

                errors.append(
                    {
                        "detail": "Opening hours do not match between Kirkanta and the database",
                        "schedule_raw": schedule,
                        "schedule_date": schedule_date,
                        "schedule_period": schedule.get("period"),
                        "override": override,
                        "kirkanta_opening_hours": expected_time_elements,
                        "database_opening_hours": current_date_opening_hours,
                    }
                )
                is_ok = False

        if raise_exception and errors:
            raise KirjastotValidationError(
                f'Data validation failed for library "{library.name}"',
                errors=errors,
            )

        return is_ok

    def process_kirkanta_period(
        self, library: Resource, kirkanta_period: AnnotatedKirkantaPeriod
    ) -> (list[dict], bool):
        valid_from = None
        valid_until = None
        has_fixed_periods = False
        if kirkanta_period["validFrom"]:
            valid_from = parse(kirkanta_period["validFrom"]).date()
        if kirkanta_period["validUntil"]:
            valid_until = parse(kirkanta_period["validUntil"]).date()

        self.logger.debug(
            'period #{} "{}": {} - {}'.format(
                kirkanta_period["id"],
                kirkanta_period.get("name", ""),
                valid_from,
                valid_until,
            )
        )

        if valid_from is not None and valid_until is not None:
            time_delta = valid_until - valid_from

            if (
                time_delta.days < 7
                or kirkanta_period["id"] in KIRKANTA_LONG_EXCEPTIONAL_PERIODS
            ):
                self.logger.debug("Importing as separate days.")
                periods = self.separate_exceptional_periods(library, kirkanta_period)
                return periods, has_fixed_periods

        self.logger.debug("Importing as a longer period.")

        override = False
        if all([d.get("closed", True) for d in kirkanta_period["days"]]):
            override = True
            state = State.CLOSED
        else:
            state = State.UNDEFINED

        if kirkanta_period["isException"]:
            override = True

        long_period = {
            "resource": library,
            "name": {"fi": kirkanta_period.get("name", "")},
            "start_date": valid_from,
            "end_date": valid_until,
            "resource_state": state,
            "override": override,
            "origins": [
                {
                    "data_source_id": self.data_source.id,
                    "origin_id": str(kirkanta_period["id"]),
                }
            ],
            "time_span_groups": self.get_openings(
                kirkanta_period["days"], period_start=valid_from
            ),
        }

        if kirkanta_period["id"] in KIRKANTA_FIXED_GROUPS:
            long_period["time_span_groups"] = KIRKANTA_FIXED_GROUPS[
                kirkanta_period["id"]
            ]
            has_fixed_periods = True

        return [long_period], has_fixed_periods

    def do_import(self):
        libraries = Resource.objects.filter(origins__data_source=self.data_source)

        if self.options.get("single", None):
            libraries = libraries.filter(origins__origin_id=self.options["single"])

        start_date = self.options.get("date", None)

        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        self.logger.info("{} libraries found".format(libraries.count()))

        import_start_date, import_end_date = self.get_date_range(
            start=start_date, back=0
        )

        for library in libraries:
            self.logger.info(
                'Importing hours for "{}" id:{}...'.format(library.name, library.id)
            )
            queryset = (
                DatePeriod.objects.filter(
                    origins__data_source=self.data_source, resource=library
                )
                .filter(Q(end_date=None) | Q(end_date__gte=import_start_date))
                .distinct()
                .prefetch_related("origins", "time_span_groups__time_spans")
            )
            syncher = ModelSyncher(
                queryset,
                data_source=self.data_source,
                delete_func=self.mark_deleted,
                check_deleted_func=self.check_deleted,
            )
            has_fixed_periods = False

            kirkanta_data = self.get_hours_from_api(
                library, import_start_date, import_end_date
            )
            kirkanta_periods = self.get_kirkanta_periods(kirkanta_data)

            periods = []
            for kirkanta_period in kirkanta_periods.values():
                processed_periods, found_fixed_periods = self.process_kirkanta_period(
                    library, kirkanta_period
                )
                periods.extend(processed_periods)
                has_fixed_periods = has_fixed_periods or found_fixed_periods

            try:
                with transaction.atomic():
                    # save_dateperiod does a lot more than just save the period,
                    # so we need to save them all first and then check them.
                    saved_periods = []
                    for period_data in periods:
                        period = self.save_dateperiod(period_data)
                        saved_periods.append(period)

                    self.logger.info(
                        f'Checking hours for "{library.name}" [ID: {library.id}]...'
                    )
                    self.check_library_data(
                        library,
                        saved_periods,
                        kirkanta_data,
                        import_start_date,
                        import_end_date,
                        has_fixed_periods,
                    )
                    self.logger.info("Check OK.")
                    self.logger.info(
                        f'Syncing hours for "{library.name}" [ID: {library.id}]...'
                    )
                    # Validation passed, sync the data, i.e. delete all unsaved periods.
                    for period in saved_periods:
                        # Mark the period to not be deleted.
                        syncher.mark(period)
                    syncher.finish(force=self.options["force"])

                    self.logger.info(
                        f'Imported hours for "{library.name}" [ID: {library.id}]'
                    )

            except KirjastotValidationError as e:
                self.logger.exception(
                    f'Library data import failed for library "{library.name}" [ID: {library.id}]\n'
                    f"Check that the library has correct opening hours in Kirkanta.\n",
                    extra={
                        "library.id": library.id,
                        "library.name": library.name,
                        "errors": e.errors,
                    },
                )
                self._errors.append(e)
                continue

    @db.transaction.atomic
    def import_openings(self):
        with DeferUpdatingDenormalizedDatePeriodData():
            self.do_import()
        if self._errors:
            self.logger.warning(f"Import finished with {len(self._errors)} errors.")
        else:
            self.logger.info("Import finished.")

    def import_check(self):
        libraries = Resource.objects.filter(origins__data_source=self.data_source)

        if self.options.get("single", None):
            libraries = libraries.filter(origins__origin_id=self.options["single"])

        start_date = self.options.get("date", None)

        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        self.logger.info("{} libraries found".format(libraries.count()))

        import_start_date, import_end_date = self.get_date_range(
            start=start_date, back=0
        )

        for library in libraries:
            self.logger.info(
                'Fetching schedule for "{}" id:{}...'.format(library.name, library.id)
            )
            data = self.get_hours_from_api(library, import_start_date, import_end_date)

            is_ok = self.check_library_data(
                library,
                list(library.date_periods.all()),
                data,
                import_start_date,
                import_end_date,
                has_fixed_periods=False,
                raise_exception=False,
            )
            if is_ok:
                self.logger.info("Check OK.")
            else:
                self.logger.warning("Check failed.")
