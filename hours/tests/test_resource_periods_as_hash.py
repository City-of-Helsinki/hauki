import datetime

import pytest

from hours.enums import RuleContext, RuleSubject, State, Weekday
from hours.models import DatePeriod, Rule, TimeSpan
from hours.tests.conftest import (
    DatePeriodFactory,
    RuleFactory,
    TimeSpanFactory,
    TimeSpanGroupFactory,
)

NO_DATE_PERIODS_HASH = "d41d8cd98f00b204e9800998ecf8427e"


@pytest.mark.django_db
@pytest.mark.parametrize("model", [DatePeriod, TimeSpan, Rule])
def test_hash_input_should_not_include_name_or_description(model):
    instance = model()
    hash_input = instance.as_hash_input()
    instance.name = "Test name"
    assert instance.as_hash_input() == hash_input
    instance.description = "Test description"
    assert instance.as_hash_input() == hash_input


@pytest.mark.django_db
def test_resource_date_periods_hash_no_date_periods(resource):
    assert resource.date_periods_hash == NO_DATE_PERIODS_HASH
    assert resource._get_date_periods_as_hash() == NO_DATE_PERIODS_HASH


@pytest.mark.django_db
def test_resource_date_periods_hash_one_date_period(resource):
    DatePeriodFactory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    assert resource._get_date_periods_as_hash() == "61615497a62efac75cbbff6e77a6cb6e"


@pytest.mark.django_db
def test_resource_date_periods_hash_name_and_description_ignored(resource):
    date_period = DatePeriodFactory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    expected_hash = "61615497a62efac75cbbff6e77a6cb6e"
    assert resource._get_date_periods_as_hash() == expected_hash

    date_period.name = "Changed name"
    date_period.save()

    assert resource._get_date_periods_as_hash() == expected_hash

    date_period.description = "Changed description"
    date_period.save()

    assert resource._get_date_periods_as_hash() == expected_hash


@pytest.mark.django_db
def test_resource_date_periods_hash_two_resources_should_have_same_hash(
    resource_factory,
):
    resources = [resource_factory(), resource_factory()]

    for resource in resources:
        DatePeriodFactory(
            resource=resource,
            resource_state=State.OPEN,
            start_date=datetime.date(year=2021, month=1, day=1),
            end_date=datetime.date(year=2022, month=12, day=31),
        )

    assert (
        resources[0]._get_date_periods_as_hash()
        == resources[1]._get_date_periods_as_hash()
    )


@pytest.mark.django_db
def test_resource_date_periods_hash_is_kept_up_to_date(resource):
    assert resource.date_periods_hash == NO_DATE_PERIODS_HASH
    hashes = set()

    date_period = DatePeriodFactory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    assert resource.date_periods_hash
    assert resource.date_periods_hash not in hashes
    hashes.add(resource.date_periods_hash)

    date_period.resource_state = State.CLOSED
    date_period.save()

    assert resource.date_periods_hash
    assert resource.date_periods_hash not in hashes
    hashes.add(resource.date_periods_hash)

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        weekdays=[Weekday.MONDAY],
        resource_state=State.OPEN,
    )

    assert resource.date_periods_hash
    assert resource.date_periods_hash not in hashes
    hashes.add(resource.date_periods_hash)

    RuleFactory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_ordinal=2,
    )

    assert resource.date_periods_hash
    assert resource.date_periods_hash not in hashes
