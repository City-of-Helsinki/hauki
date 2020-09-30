from datetime import date, time, timedelta
from random import randrange

import pytest
from psycopg2.extras import DateRange
from rest_framework.test import APIClient

from hours.models import DataSource, Opening, Period, Status, Target, Weekday


def random_date(start, end):
    delta = end - start
    random_date = randrange(delta.days)
    return start + timedelta(days=random_date)


def random_hour(start, end):
    start_hour = start.hour
    end_hour = end.hour
    if end_hour < start_hour:
        end_hour = end_hour + 24
    delta = end_hour - start_hour
    random_time = randrange(delta)
    return time((start_hour + random_time) % 24)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def data_source():
    return DataSource.objects.create(id="ds1")


@pytest.fixture
def another_data_source():
    return DataSource.objects.create(id="ds2")


@pytest.fixture
def target(data_source):
    def _target(origin_id):
        target_id = f"{data_source.id}:{origin_id}"
        return Target(
            id=target_id,
            data_source=data_source,
            origin_id=origin_id,
            name="Kallion kirjasto",
        )

    return _target


@pytest.fixture
def another_target(another_data_source):
    def _target(origin_id):
        target_id = f"{another_data_source.id}:{origin_id}"
        return Target(
            id=target_id,
            data_source=another_data_source,
            origin_id=origin_id,
            name="Ryhmätyötila Otso",
        )

    return _target


@pytest.fixture
def long_period(data_source):
    def _long_period(target, origin_id):
        period_id = f"{data_source.id}:{origin_id}"
        start = random_date(date(2020, 1, 1), date(2020, 12, 31))
        end = random_date(date(2022, 1, 1), date(2022, 12, 31))
        return Period(
            id=period_id,
            data_source=data_source,
            origin_id=origin_id,
            target=target,
            period=DateRange(lower=start, upper=end, bounds="[]"),
        )

    return _long_period


@pytest.fixture
def medium_period(data_source):
    def _medium_period(target, origin_id):
        period_id = f"{data_source.id}:{origin_id}"
        start = random_date(date(2021, 1, 1), date(2021, 5, 31))
        end = random_date(date(2021, 9, 1), date(2021, 12, 31))
        return Period(
            id=period_id,
            data_source=data_source,
            origin_id=origin_id,
            target=target,
            period=DateRange(lower=start, upper=end, bounds="[]"),
        )

    return _medium_period


@pytest.fixture
def short_period(data_source):
    def _short_period(target, origin_id):
        period_id = f"{data_source.id}:{origin_id}"
        start = random_date(date(2021, 7, 10), date(2021, 7, 15))
        end = random_date(date(2021, 7, 16), date(2021, 7, 20))
        return Period(
            id=period_id,
            data_source=data_source,
            origin_id=origin_id,
            target=target,
            period=DateRange(lower=start, upper=end, bounds="[]"),
        )

    return _short_period


@pytest.fixture
def late_period(data_source):
    def _late_period(target, origin_id):
        period_id = f"{data_source.id}:{origin_id}"
        start = random_date(date(2022, 7, 1), date(2022, 9, 30))
        end = random_date(date(2022, 10, 1), date(2022, 12, 31))
        return Period(
            id=period_id,
            data_source=data_source,
            origin_id=origin_id,
            target=target,
            period=DateRange(lower=start, upper=end, bounds="[]"),
        )

    return _late_period


@pytest.fixture
def period_first_week_opening(data_source):
    def _opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)

    return _opening


@pytest.fixture
def period_second_week_opening(data_source):
    def _opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(
            weekday=weekday, period=period, opens=opens, closes=closes, week=2
        )

    return _opening


@pytest.fixture
def period_second_week_closing(data_source):
    def _opening(period, weekday):
        return Opening(weekday=weekday, period=period, status=Status.CLOSED, week=2)

    return _opening


@pytest.fixture
def period_monthly_opening(data_source):
    def _opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(
            weekday=weekday, period=period, opens=opens, closes=closes, week=1, month=1
        )

    return _opening


@pytest.fixture
def period_second_monthly_opening(data_source):
    def _opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(
            weekday=weekday, period=period, opens=opens, closes=closes, week=3, month=1
        )

    return _opening


@pytest.fixture
def targets(db, target):
    values = []
    for id in range(1, 11):
        values.append(target(str(id)))
    return Target.objects.bulk_create(values)


@pytest.fixture
def more_targets(db, another_target):
    values = []
    for id in range(1, 11):
        values.append(another_target(str(id)))
    return Target.objects.bulk_create(values)


@pytest.fixture
def periods(targets, long_period, medium_period, short_period, late_period):
    values = []
    for target in targets:
        # each target should have long and medium range and some exceptions
        values.append(long_period(target, target.origin_id))
        values.append(medium_period(target, f"{target.origin_id}-medium"))
        values.append(short_period(target, f"{target.origin_id}-short1"))
        values.append(short_period(target, f"{target.origin_id}-short2"))
        values.append(late_period(target, f"{target.origin_id}-late"))
    return Period.objects.bulk_create(values)


@pytest.fixture
def first_opening():
    def _first_opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)

    return _first_opening


@pytest.fixture
def second_opening():
    def _second_opening(period, weekday):
        opens = random_hour(time(14), time(16))
        closes = random_hour(time(18), time(20))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)

    return _second_opening


@pytest.fixture
def third_opening():
    def _third_opening(period, weekday):
        opens = random_hour(time(21), time(23))
        closes = random_hour(time(1), time(4))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)

    return _third_opening


@pytest.fixture
def openings(periods, first_opening, second_opening, third_opening):
    values = []
    for index, period in enumerate(periods):
        for weekday in Weekday.choices:
            values.append(first_opening(period, weekday[0]))
        # add some extra spice
        if index % 10 == 0:
            values.append(second_opening(period, weekday[0]))
        # wow, this is a rare case
        if index % 50 == 0:
            values.append(third_opening(period, weekday[0]))
    return Opening.objects.bulk_create(values)
