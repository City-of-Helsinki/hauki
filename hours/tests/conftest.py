import pytest
from hours.models import Weekday, DataSource, Target, Period, Opening
from psycopg2.extras import DateRange
from random import randrange
from datetime import timedelta, date, time

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
    return time((start_hour+random_time) % 24)

@pytest.fixture
def data_source():
    return DataSource.objects.create(id='ds1')

@pytest.fixture(scope='session')
def session_data_source():
    return DataSource.objects.create(id='ds1')

@pytest.fixture(scope='session')
def target(session_data_source):
    def _target(origin_id):
        target_id = f'{session_data_source.id}:{origin_id}'
        return Target(id=target_id, data_source=session_data_source, origin_id=origin_id,
                      name='Kallion kirjasto')
    return _target

@pytest.fixture(scope='session')
def targets(target):
    values = []
    for id in range(1,1000):
        values.append(target(id))
    return Target.objects.bulk_create(values)

@pytest.fixture(scope='session')
def long_period(session_data_source):
    def _long_period(target, origin_id):
        period_id = f'{session_data_source.id}:{origin_id}'
        start = random_date(date(2020,1,1), date(2020,12,31))
        end = random_date(date(2022,1,1), date(2022,12,31))
        return Period(id=period_id, data_source=session_data_source, origin_id=origin_id,
                      target=target, period=DateRange(lower=start, upper=end))
    return _long_period

@pytest.fixture(scope='session')
def medium_period(session_data_source):
    def _medium_period(target, origin_id):
        period_id = f'{session_data_source.id}:{origin_id}'
        start = random_date(date(2021,1,1), date(2021,5,31))
        end = random_date(date(2021,9,1), date(2021,12,31))
        return Period(id=period_id, data_source=session_data_source, origin_id=origin_id,
                      target=target, period=DateRange(lower=start, upper=end))
    return _medium_period

@pytest.fixture(scope='session')
def short_period(session_data_source):
    def _short_period(target, origin_id):
        period_id = f'{session_data_source.id}:{origin_id}'
        start = random_date(date(2021,7,10), date(2021,7,15))
        end = random_date(date(2021,7,16), date(2021,7,20))
        return Period(id=period_id, data_source=session_data_source, origin_id=origin_id,
                      target=target, period=DateRange(lower=start, upper=end))
    return _short_period

@pytest.fixture(scope='session')
def periods(targets, long_period, medium_period, short_period):
    values = []
    for target in targets:
        # each target should have long and medium range and some exceptions
        values.append(long_period(target, target.origin_id))
        values.append(medium_period(target, f'{target.origin_id}-medium'))
        values.append(short_period(target, f'{target.origin_id}-short1'))
        values.append(short_period(target, f'{target.origin_id}-short2'))
    return Period.objects.bulk_create(values)

@pytest.fixture(scope='session')
def first_opening():
    def _first_opening(period, weekday):
        opens = random_hour(time(7), time(8))
        closes = random_hour(time(10), time(13))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)
    return _first_opening

@pytest.fixture(scope='session')
def second_opening():
    def _second_opening(period, weekday):
        opens = random_hour(time(14), time(16))
        closes = random_hour(time(18), time(20))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)
    return _second_opening

@pytest.fixture(scope='session')
def third_opening():
    def _third_opening(period, weekday):
        opens = random_hour(time(21), time(23))
        closes = random_hour(time(1), time(4))
        return Opening(weekday=weekday, period=period, opens=opens, closes=closes)
    return _third_opening

@pytest.fixture(scope='session')
def openings(periods, first_opening, second_opening, third_opening):
    values = []
    for index, period in enumerate(periods):
        for weekday in Weekday.choices:
            values.append(first_opening(period, weekday[0]))
        if index % 10 == 0:
            values.append(second_opening(period, weekday[0]))
        if index % 100 == 0:
            values.append(third_opening(period, weekday[0]))
    return Opening.objects.bulk_create(values)