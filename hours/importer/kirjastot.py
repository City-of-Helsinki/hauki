from collections import defaultdict
from datetime import date, datetime, time
from itertools import groupby
from operator import itemgetter

import holidays
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django import db
from django.utils import timezone

from ..enums import RuleContext, RuleSubject, State, Weekday
from ..models import DataSource, Resource, TimeElement, combine_element_time_spans
from .base import Importer, register_importer

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


@register_importer
class KirjastotImporter(Importer):
    name = "kirjastot"

    def setup(self):
        self.URL_BASE = "https://api.kirjastot.fi/v4/"
        ds_args = dict(id="kirkanta")
        defaults = dict(name="kirjastot.fi")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )

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

        begin = (start - relativedelta(months=back)).replace(day=1)
        end = (start + relativedelta(months=forward)).replace(day=1)

        return begin, end

    def get_hours_from_api(self, resource: Resource, start: date, end: date) -> dict:
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
        data = self.api_get("library", kirkanta_id, params)

        if data["total"] > 0:
            return data

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
        for (weekday, pattern) in repetition_pattern.items():
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
        for (weekday, pattern) in repetition_pattern.items():
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
            for (rotation_week_num, week_opening_times) in enumerate(openings_by_week):
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
                        if not opening_time[0] and not opening_time[1]:
                            full_day = True

                        time_spans.append(
                            {
                                "group": None,
                                "start_time": opening_time[0]
                                if opening_time[0]
                                else None,
                                "end_time": opening_time[1]
                                if opening_time[1]
                                else None,
                                "weekdays": [i["weekday"] for i in opening_times],
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
                    "name": period.get("name"),
                    "start_date": parse(period["validFrom"]).date(),
                    "end_date": parse(period["validUntil"]).date(),
                    "resource_state": State.CLOSED,
                    "override": True,
                }
            ]

        periods = []
        for day in period["days"]:
            period = {
                "resource": resource,
                "name": day.get("info"),
                "start_date": day["date"],
                "end_date": day["date"],
                "resource_state": State.UNDEFINED,
                "override": True,
            }
            if day["closed"]:
                period["resource_state"] = State.CLOSED
                periods.append(period)
                continue

            time_spans = []
            for opening_time in day["times"]:
                time_spans.append(
                    {
                        "group": None,
                        "start_time": opening_time["from"],
                        "end_time": opening_time["to"],
                        "resource_state": KIRKANTA_STATUS_MAP[opening_time["status"]],
                        "name": day.get("info"),
                    }
                )
            period["time_span_groups"] = [
                {
                    "time_spans": time_spans,
                    "rules": [],
                }
            ]
            periods.append(period)

        return periods

    def get_kirkanta_periods(self, data: dict) -> dict:
        """
        Annotates kirkanta data so that periods contain indexed data for each day for
        their duration. Returned periods may contain empty days or days belonging to
        other periods, since original data may have period overlaps.
        """
        periods = data.get("refs", {}).get("period", None)
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
                    "Period {} not found in periods! Skipping days {}".format(
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

    def check_library_data(self, library, data, start_date, end_date):
        """Checks that the daily opening hours match the schedule in the data
        Raises AssertionError if they don't match"""
        override_periods = []
        kirkanta_periods = data.get("refs", {}).get("period", None)

        schedules = data.get("data", {}).get("schedules")

        if not schedules:
            self.logger.info("No schedules found in the incoming data. Skipping.")
            return

        for kirkanta_period in kirkanta_periods.values():
            valid_from = None
            valid_until = None
            if kirkanta_period["validFrom"]:
                valid_from = parse(kirkanta_period["validFrom"]).date()
            if kirkanta_period["validUntil"]:
                valid_until = parse(kirkanta_period["validUntil"]).date()

            if valid_from is not None and valid_until is not None:
                time_delta = valid_until - valid_from
                if time_delta.days < 7:
                    override_periods.append(kirkanta_period["id"])
                    continue

            period_schedules = [
                i for i in schedules if i.get("period") == kirkanta_period["id"]
            ]

            if all([d["closed"] for d in period_schedules]):
                override_periods.append(kirkanta_period["id"])

            if kirkanta_period["isException"]:
                override_periods.append(kirkanta_period["id"])

        opening_hours = library.get_daily_opening_hours(start_date, end_date)

        for schedule in schedules:
            time_elements = []

            if schedule.get("closed") is True:
                time_elements.append(
                    TimeElement(
                        start_time=None,
                        end_time=None,
                        resource_state=State.CLOSED,
                        override=True
                        if schedule.get("period") in override_periods
                        else False,
                        full_day=True,
                    )
                )
            else:
                for schedule_time in schedule.get("times"):
                    try:
                        start_time = datetime.strptime(
                            schedule_time.get("from"), "%H:%M"
                        ).time()
                    except ValueError:
                        start_time = None
                    try:
                        end_time = datetime.strptime(
                            schedule_time.get("to"), "%H:%M"
                        ).time()
                    except ValueError:
                        end_time = None

                    time_elements.append(
                        TimeElement(
                            start_time=start_time,
                            end_time=end_time,
                            resource_state=KIRKANTA_STATUS_MAP[schedule_time["status"]],
                            override=True
                            if schedule.get("period") in override_periods
                            else False,
                            full_day=False,
                        )
                    )

            schedule_date = schedule.get("date")
            if not isinstance(schedule_date, date):
                schedule_date = parse(schedule.get("date")).date()

            time_elements = combine_element_time_spans(time_elements)

            time_elements.sort(key=self._get_times_for_sort)
            opening_hours[schedule_date].sort(key=self._get_times_for_sort)

            assert time_elements == opening_hours[schedule_date]

    @db.transaction.atomic
    def import_openings(self):
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
            has_fixed_periods = False
            self.logger.info(
                'Importing hours for "{}" id:{}...'.format(library.name, library.id)
            )

            data = self.get_hours_from_api(library, import_start_date, import_end_date)

            kirkanta_periods = self.get_kirkanta_periods(data)

            periods = []
            for kirkanta_period in kirkanta_periods.values():
                valid_from = None
                valid_until = None
                if kirkanta_period["validFrom"]:
                    valid_from = parse(kirkanta_period["validFrom"]).date()
                if kirkanta_period["validUntil"]:
                    valid_until = parse(kirkanta_period["validUntil"]).date()

                self.logger.debug(
                    'period #{} "{}": {} - {}'.format(
                        kirkanta_period["id"],
                        kirkanta_period["name"],
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
                        periods.extend(
                            self.separate_exceptional_periods(library, kirkanta_period)
                        )
                        continue

                self.logger.debug("Importing as a longer period.")

                override = False
                if all([d.get("closed", True) for d in kirkanta_period["days"]]):
                    override = True

                if kirkanta_period["isException"]:
                    override = True

                long_period = {
                    "resource": library,
                    "name": kirkanta_period.get("name"),
                    "start_date": valid_from,
                    "end_date": valid_until,
                    "resource_state": State.UNDEFINED,
                    "override": override,
                    "time_span_groups": self.get_openings(
                        kirkanta_period["days"], period_start=valid_from
                    ),
                }

                if kirkanta_period["id"] in KIRKANTA_FIXED_GROUPS:
                    long_period["time_span_groups"] = KIRKANTA_FIXED_GROUPS[
                        kirkanta_period["id"]
                    ]
                    has_fixed_periods = True

                periods.append(long_period)

            for period_data in periods:
                self.save_period(period_data)

            self.logger.info(
                "Checking that the imported date periods match the data..."
            )
            if has_fixed_periods:
                self.logger.info(
                    "Not checking because library has fixed periods in the importer."
                )
            else:
                self.check_library_data(
                    library, data, import_start_date, import_end_date
                )
                self.logger.info("Check OK.")

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

            self.check_library_data(library, data, import_start_date, import_end_date)
            self.logger.info("Check OK.")
