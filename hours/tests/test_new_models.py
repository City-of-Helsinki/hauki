import datetime

import pytest
from django.core.exceptions import ValidationError

from hours.enums import FrequencyModifier, RuleContext, RuleSubject, State, Weekday
from hours.models import TimeElement


@pytest.mark.django_db
def test_resource_get_daily_opening_hours(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.business_days(),
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        weekdays=Weekday.weekend(),
    )

    weekday_time_element = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    weekend_time_element = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=18),
    ) == {
        datetime.date(year=2020, month=10, day=12): [weekday_time_element],
        datetime.date(year=2020, month=10, day=13): [weekday_time_element],
        datetime.date(year=2020, month=10, day=14): [weekday_time_element],
        datetime.date(year=2020, month=10, day=15): [weekday_time_element],
        datetime.date(year=2020, month=10, day=16): [weekday_time_element],
        datetime.date(year=2020, month=10, day=17): [weekend_time_element],
        datetime.date(year=2020, month=10, day=18): [weekend_time_element],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_periods_in_result(
    assert_count_equal,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=17, minute=0),
        weekdays=Weekday.business_days(),
        resource_state=State.OPEN,
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=10, minute=0),
        weekdays=Weekday.business_days(),
        resource_state=State.SELF_SERVICE,
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=17, minute=0),
        end_time=datetime.time(hour=19, minute=0),
        weekdays=Weekday.business_days(),
        resource_state=State.SELF_SERVICE,
    )

    weekday_time_element_open = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=17, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )
    weekday_time_element_self_service_morning = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=10, minute=0),
        end_time_on_next_day=False,
        resource_state=State.SELF_SERVICE,
        override=False,
        full_day=False,
    )

    weekday_time_element_self_service_evening = TimeElement(
        start_time=datetime.time(hour=17, minute=0),
        end_time=datetime.time(hour=19, minute=0),
        end_time_on_next_day=False,
        resource_state=State.SELF_SERVICE,
        override=False,
        full_day=False,
    )

    opening_hours = resource.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=12),
    )

    assert list(opening_hours.keys()) == [datetime.date(year=2020, month=10, day=12)]
    assert_count_equal(
        opening_hours[datetime.date(year=2020, month=10, day=12)],
        [
            weekday_time_element_open,
            weekday_time_element_self_service_morning,
            weekday_time_element_self_service_evening,
        ],
    )

    periods = [
        i.periods for i in opening_hours[datetime.date(year=2020, month=10, day=12)]
    ]
    assert periods == [[date_period], [date_period], [date_period]]


@pytest.mark.django_db
def test_get_period_for_date(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=1, day=1),
        datetime.date(year=2020, month=1, day=1),
    ) == {
        datetime.date(year=2020, month=1, day=1): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }


@pytest.mark.django_db
def test_get_period_for_date_with_rule(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.weekend(),
    )

    rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
    )

    # Monday or Sunday not matching because rule limits the days only to thursdays
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=5),
            datetime.date(year=2020, month=10, day=5),
        )
        == {}
    )
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=18),
            datetime.date(year=2020, month=10, day=18),
        )
        == {}
    )

    # Thursday
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=15),
    ) == {
        datetime.date(year=2020, month=10, day=15): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }

    # The whole week
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=18),
    ) == {
        datetime.date(year=2020, month=10, day=15): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }


@pytest.mark.django_db
def test_get_infinite_period_for_date_with_rule(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=None,
        end_date=None,
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.weekend(),
    )

    # period has no start date, so context cannot be period
    rule_factory(
        group=time_span_group,
        context=RuleContext.MONTH,
        subject=RuleSubject.THURSDAY,
        frequency_modifier=FrequencyModifier.ODD,
    )

    # Monday or Sunday not matching because rule limits the days only to thursdays
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=5),
            datetime.date(year=2020, month=10, day=5),
        )
        == {}
    )
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=18),
            datetime.date(year=2020, month=10, day=18),
        )
        == {}
    )

    # Odd Thursday
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=15),
    ) == {
        datetime.date(year=2020, month=10, day=15): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }

    # Even Thursday
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=22),
            datetime.date(year=2020, month=10, day=22),
        )
        == {}
    )

    # Odd week
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=18),
    ) == {
        datetime.date(year=2020, month=10, day=15): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }

    # Even week
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=19),
            datetime.date(year=2020, month=10, day=25),
        )
        == {}
    )


@pytest.mark.django_db
def test_get_period_for_dates_with_two_rules(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.MONTH,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    # Odd Thursday in even month
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=11),
            datetime.date(year=2020, month=10, day=17),
        )
        == {}
    )

    # Odd Thursday in odd month
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=9, day=14),
            datetime.date(year=2020, month=9, day=20),
        )
        == {}
    )

    # Even Thursday in even month
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=18),
        datetime.date(year=2020, month=10, day=25),
    ) == {
        datetime.date(year=2020, month=10, day=22): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }

    # Even Thursday in odd month
    assert (
        date_period.get_daily_opening_hours(
            datetime.date(year=2020, month=9, day=21),
            datetime.date(year=2020, month=9, day=28),
        )
        == {}
    )


@pytest.mark.django_db
def test_get_period_for_dates_with_two_time_span_groups(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)
    other_time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    time_span_factory(
        group=other_time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.business_days(),
    )

    rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        frequency_modifier=FrequencyModifier.ODD,
    )

    rule_factory(
        group=other_time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    # The odd week
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=18),
    ) == {
        datetime.date(year=2020, month=10, day=15): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=18, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }

    # The even week
    assert date_period.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=19),
        datetime.date(year=2020, month=10, day=25),
    ) == {
        datetime.date(year=2020, month=10, day=22): [
            TimeElement(
                start_time=datetime.time(hour=10, minute=0),
                end_time=datetime.time(hour=16, minute=0),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }


@pytest.mark.django_db
def test_rule_fail_infinite_period_context(
    resource,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=None,
        end_date=None,
    )

    time_span_group = time_span_group_factory(period=date_period)

    # period has no start date, so context cannot be period
    with pytest.raises(ValidationError):
        rule_factory(
            group=time_span_group,
            context=RuleContext.PERIOD,
            subject=RuleSubject.THURSDAY,
            frequency_modifier=FrequencyModifier.ODD,
        )


@pytest.mark.django_db
def test_rule_fail_both_ordinal_and_modifier(
    resource,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    # rule cannot have both frequency ordinal and modifier
    with pytest.raises(ValidationError):
        rule_factory(
            group=time_span_group,
            context=RuleContext.PERIOD,
            subject=RuleSubject.THURSDAY,
            frequency_modifier=FrequencyModifier.ODD,
            frequency_ordinal=3,
        )


@pytest.mark.django_db
def test_rule_fail_negative_start(
    resource,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    # rule cannot start from a negative index
    with pytest.raises(ValidationError):
        rule_factory(
            group=time_span_group,
            context=RuleContext.PERIOD,
            subject=RuleSubject.THURSDAY,
            frequency_ordinal=3,
            start=-1,
        )


@pytest.mark.django_db
def test_rule_fail_both_start_and_modifier(
    resource,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    # rule cannot have both start and frequency modifier
    with pytest.raises(ValidationError):
        rule_factory(
            group=time_span_group,
            context=RuleContext.PERIOD,
            subject=RuleSubject.THURSDAY,
            frequency_modifier=FrequencyModifier.ODD,
            start=3,
        )


@pytest.mark.django_db
def test_rule_filter_dates1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=10, day=8),
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=22),
        datetime.date(year=2020, month=10, day=29),
    }


@pytest.mark.django_db
def test_rule_filter_dates1_2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        start=1,
    )

    start_date = datetime.date(year=2020, month=1, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=1, day=2),
    }


@pytest.mark.django_db
def test_rule_filter_dates1_3(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        start=2,
        frequency_ordinal=3,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=8),
        datetime.date(year=2020, month=10, day=29),
    }


@pytest.mark.django_db
def test_rule_filter_dates1_4(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    # start is missing from rule with ordinal, should default to 1
    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.THURSDAY,
        frequency_ordinal=3,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule.start == 1
    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=10, day=22),
    }


@pytest.mark.django_db
def test_rule_filter_dates2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.MONTH,
        subject=RuleSubject.DAY,
        start=1,
    )

    start_date = datetime.date(year=2020, month=9, day=1)
    end_date = datetime.date(year=2020, month=11, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=9, day=1),
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=11, day=1),
    }


@pytest.mark.django_db
def test_rule_filter_dates3(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.MONTH,
        subject=RuleSubject.WEDNESDAY,
        start=1,
    )

    start_date = datetime.date(year=2020, month=9, day=1)
    end_date = datetime.date(year=2020, month=11, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=9, day=2),
        datetime.date(year=2020, month=10, day=7),
        datetime.date(year=2020, month=11, day=4),
    }


@pytest.mark.django_db
def test_rule_filter_dates4(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=10, day=2),
        datetime.date(year=2020, month=10, day=3),
        datetime.date(year=2020, month=10, day=4),
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=13),
        datetime.date(year=2020, month=10, day=14),
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=16),
        datetime.date(year=2020, month=10, day=17),
        datetime.date(year=2020, month=10, day=18),
        datetime.date(year=2020, month=10, day=26),
        datetime.date(year=2020, month=10, day=27),
        datetime.date(year=2020, month=10, day=28),
        datetime.date(year=2020, month=10, day=29),
        datetime.date(year=2020, month=10, day=30),
        datetime.date(year=2020, month=10, day=31),
    }


@pytest.mark.django_db
def test_rule_filter_dates4_2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=None,
        end_date=None,
    )

    time_span_group = time_span_group_factory(period=date_period)

    # period has no start date, so context cannot be period
    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=10, day=2),
        datetime.date(year=2020, month=10, day=3),
        datetime.date(year=2020, month=10, day=4),
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=13),
        datetime.date(year=2020, month=10, day=14),
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=16),
        datetime.date(year=2020, month=10, day=17),
        datetime.date(year=2020, month=10, day=18),
        datetime.date(year=2020, month=10, day=26),
        datetime.date(year=2020, month=10, day=27),
        datetime.date(year=2020, month=10, day=28),
        datetime.date(year=2020, month=10, day=29),
        datetime.date(year=2020, month=10, day=30),
        datetime.date(year=2020, month=10, day=31),
    }


@pytest.mark.django_db
def test_rule_filter_dates5(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.ODD,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=5),
        datetime.date(year=2020, month=10, day=6),
        datetime.date(year=2020, month=10, day=7),
        datetime.date(year=2020, month=10, day=8),
        datetime.date(year=2020, month=10, day=9),
        datetime.date(year=2020, month=10, day=10),
        datetime.date(year=2020, month=10, day=11),
        datetime.date(year=2020, month=10, day=19),
        datetime.date(year=2020, month=10, day=20),
        datetime.date(year=2020, month=10, day=21),
        datetime.date(year=2020, month=10, day=22),
        datetime.date(year=2020, month=10, day=23),
        datetime.date(year=2020, month=10, day=24),
        datetime.date(year=2020, month=10, day=25),
    }


@pytest.mark.django_db
def test_rule_filter_dates5_2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=None,
        end_date=None,
    )

    time_span_group = time_span_group_factory(period=date_period)

    # period has no start date, so context cannot be period
    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.ODD,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=5),
        datetime.date(year=2020, month=10, day=6),
        datetime.date(year=2020, month=10, day=7),
        datetime.date(year=2020, month=10, day=8),
        datetime.date(year=2020, month=10, day=9),
        datetime.date(year=2020, month=10, day=10),
        datetime.date(year=2020, month=10, day=11),
        datetime.date(year=2020, month=10, day=19),
        datetime.date(year=2020, month=10, day=20),
        datetime.date(year=2020, month=10, day=21),
        datetime.date(year=2020, month=10, day=22),
        datetime.date(year=2020, month=10, day=23),
        datetime.date(year=2020, month=10, day=24),
        datetime.date(year=2020, month=10, day=25),
    }


@pytest.mark.django_db
def test_rule_filter_dates6(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.DAY,
        start=15,
    )

    start_date = datetime.date(year=2020, month=1, day=1)
    end_date = datetime.date(year=2020, month=1, day=31)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=1, day=15),
    }


@pytest.mark.django_db
def test_rule_filter_dates6_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        start=8,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=19),
        datetime.date(year=2020, month=10, day=20),
        datetime.date(year=2020, month=10, day=21),
        datetime.date(year=2020, month=10, day=22),
        datetime.date(year=2020, month=10, day=23),
        datetime.date(year=2020, month=10, day=24),
        datetime.date(year=2020, month=10, day=25),
    }


@pytest.mark.django_db
def test_rule_filter_dates6_2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates7(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.MONTH,
        subject=RuleSubject.WEEK,
        start=3,
    )

    start_date = datetime.date(year=2020, month=10, day=1)
    end_date = datetime.date(year=2020, month=10, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=13),
        datetime.date(year=2020, month=10, day=14),
        datetime.date(year=2020, month=10, day=15),
        datetime.date(year=2020, month=10, day=16),
        datetime.date(year=2020, month=10, day=17),
        datetime.date(year=2020, month=10, day=18),
    }


@pytest.mark.django_db
def test_rule_filter_dates7_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.MONTH,
        subject=RuleSubject.WEEK,
        start=1,
    )

    start_date = datetime.date(year=2020, month=9, day=1)
    end_date = datetime.date(year=2020, month=11, day=30)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=9, day=1),
        datetime.date(year=2020, month=9, day=2),
        datetime.date(year=2020, month=9, day=3),
        datetime.date(year=2020, month=9, day=4),
        datetime.date(year=2020, month=9, day=5),
        datetime.date(year=2020, month=9, day=6),
        datetime.date(year=2020, month=9, day=28),
        datetime.date(year=2020, month=9, day=29),
        datetime.date(year=2020, month=9, day=30),
        datetime.date(year=2020, month=10, day=1),
        datetime.date(year=2020, month=10, day=2),
        datetime.date(year=2020, month=10, day=3),
        datetime.date(year=2020, month=10, day=4),
        datetime.date(year=2020, month=10, day=26),
        datetime.date(year=2020, month=10, day=27),
        datetime.date(year=2020, month=10, day=28),
        datetime.date(year=2020, month=10, day=29),
        datetime.date(year=2020, month=10, day=30),
        datetime.date(year=2020, month=10, day=31),
        datetime.date(year=2020, month=11, day=1),
    }


@pytest.mark.django_db
def test_rule_filter_dates8(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.DAY,
        start=3,
    )

    start_date = datetime.date(year=2020, month=1, day=1)
    end_date = datetime.date(year=2020, month=12, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=1, day=3),
    }


@pytest.mark.django_db
def test_rule_filter_dates8_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.DAY,
        start=3,
    )

    start_date = datetime.date(year=2019, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2019, month=1, day=3),
        datetime.date(year=2020, month=1, day=3),
        datetime.date(year=2021, month=1, day=3),
    }


@pytest.mark.django_db
def test_rule_filter_dates9(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        start=3,
    )

    start_date = datetime.date(year=2020, month=1, day=1)
    end_date = datetime.date(year=2020, month=12, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=1, day=13),
        datetime.date(year=2020, month=1, day=14),
        datetime.date(year=2020, month=1, day=15),
        datetime.date(year=2020, month=1, day=16),
        datetime.date(year=2020, month=1, day=17),
        datetime.date(year=2020, month=1, day=18),
        datetime.date(year=2020, month=1, day=19),
    }


@pytest.mark.django_db
def test_rule_filter_dates9_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    # we should get 1st ISO week, not 0th/53rd
    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        start=1,
    )

    start_date = datetime.date(year=2021, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2021, month=1, day=4),
        datetime.date(year=2021, month=1, day=5),
        datetime.date(year=2021, month=1, day=6),
        datetime.date(year=2021, month=1, day=7),
        datetime.date(year=2021, month=1, day=8),
        datetime.date(year=2021, month=1, day=9),
        datetime.date(year=2021, month=1, day=10),
    }


@pytest.mark.django_db
def test_rule_filter_dates10(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    start_date = datetime.date(year=2020, month=11, day=1)
    end_date = datetime.date(year=2020, month=11, day=30)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=11, day=1),
        datetime.date(year=2020, month=11, day=9),
        datetime.date(year=2020, month=11, day=10),
        datetime.date(year=2020, month=11, day=11),
        datetime.date(year=2020, month=11, day=12),
        datetime.date(year=2020, month=11, day=13),
        datetime.date(year=2020, month=11, day=14),
        datetime.date(year=2020, month=11, day=15),
        datetime.date(year=2020, month=11, day=23),
        datetime.date(year=2020, month=11, day=24),
        datetime.date(year=2020, month=11, day=25),
        datetime.date(year=2020, month=11, day=26),
        datetime.date(year=2020, month=11, day=27),
        datetime.date(year=2020, month=11, day=28),
        datetime.date(year=2020, month=11, day=29),
    }


@pytest.mark.django_db
def test_rule_filter_dates10_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule1 = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    start_date = datetime.date(year=2020, month=12, day=1)
    end_date = datetime.date(year=2021, month=1, day=31)

    assert rule1.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2020, month=12, day=7),
        datetime.date(year=2020, month=12, day=8),
        datetime.date(year=2020, month=12, day=9),
        datetime.date(year=2020, month=12, day=10),
        datetime.date(year=2020, month=12, day=11),
        datetime.date(year=2020, month=12, day=12),
        datetime.date(year=2020, month=12, day=13),
        datetime.date(year=2020, month=12, day=21),
        datetime.date(year=2020, month=12, day=22),
        datetime.date(year=2020, month=12, day=23),
        datetime.date(year=2020, month=12, day=24),
        datetime.date(year=2020, month=12, day=25),
        datetime.date(year=2020, month=12, day=26),
        datetime.date(year=2020, month=12, day=27),
        datetime.date(year=2021, month=1, day=11),
        datetime.date(year=2021, month=1, day=12),
        datetime.date(year=2021, month=1, day=13),
        datetime.date(year=2021, month=1, day=14),
        datetime.date(year=2021, month=1, day=15),
        datetime.date(year=2021, month=1, day=16),
        datetime.date(year=2021, month=1, day=17),
        datetime.date(year=2021, month=1, day=25),
        datetime.date(year=2021, month=1, day=26),
        datetime.date(year=2021, month=1, day=27),
        datetime.date(year=2021, month=1, day=28),
        datetime.date(year=2021, month=1, day=29),
        datetime.date(year=2021, month=1, day=30),
        datetime.date(year=2021, month=1, day=31),
    }


@pytest.mark.django_db
def test_rule_filter_dates11(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates11_1(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2019, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    days_in_march = set()
    for year in [2019, 2020, 2021]:
        days_in_march |= {
            datetime.date(year=year, month=3, day=d) for d in range(1, 32)
        }

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates11_2(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2019, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates11_3(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=5, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == set()


@pytest.mark.django_db
def test_rule_filter_dates11_4(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=1)
    end_date = datetime.date(year=2020, month=4, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == set()


@pytest.mark.django_db
def test_rule_filter_dates12(
    resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    rule = rule_factory(
        group=time_span_group,
        context=RuleContext.YEAR,
        subject=RuleSubject.FRIDAY,
        start=2,
    )

    start_date = datetime.date(year=2019, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    assert rule.apply_to_date_range(start_date, end_date) == {
        datetime.date(year=2019, month=1, day=11),
        datetime.date(year=2020, month=1, day=10),
        datetime.date(year=2021, month=1, day=8),
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_override(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        name="The whole year",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period2 = date_period_factory(
        name="Exception for december",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
        override=True,
    )

    time_span_group2 = time_span_group_factory(period=date_period2)

    time_span_factory(
        group=time_span_group2,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    expected_time_element = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=True,
        full_day=False,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=12, day=23),
        datetime.date(year=2020, month=12, day=25),
    ) == {
        datetime.date(year=2020, month=12, day=23): [expected_time_element],
        datetime.date(year=2020, month=12, day=24): [expected_time_element],
        datetime.date(year=2020, month=12, day=25): [expected_time_element],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_multiple_full_day_overrides(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        name="The whole year",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period2 = date_period_factory(
        name="Exception for december",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
        override=True,
    )

    time_span_group2 = time_span_group_factory(period=date_period2)

    time_span_factory(
        group=time_span_group2,
        resource_state=State.CLOSED,
        weekdays=list(Weekday),
        full_day=True,
    )

    date_period3 = date_period_factory(
        name="Exceptions for december 24th and 25th",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=24),
        end_date=datetime.date(year=2020, month=12, day=25),
        override=True,
    )

    time_span_group3 = time_span_group_factory(period=date_period3)

    time_span_factory(
        group=time_span_group3,
        resource_state=State.EXIT_ONLY,
        weekdays=list(Weekday),
        full_day=True,
    )

    expected_time_element_closed = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=True,
    )

    expected_time_element_exit_only = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.EXIT_ONLY,
        override=True,
        full_day=True,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=12, day=23),
        datetime.date(year=2020, month=12, day=25),
    ) == {
        datetime.date(year=2020, month=12, day=23): [expected_time_element_closed],
        datetime.date(year=2020, month=12, day=24): [expected_time_element_exit_only],
        datetime.date(year=2020, month=12, day=25): [expected_time_element_exit_only],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_multiple_full_day_overrides_unbounded(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        name="The whole year",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period2 = date_period_factory(
        name="Exception for december forwards",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=1),
        end_date=None,
        override=True,
    )

    time_span_group2 = time_span_group_factory(period=date_period2)

    time_span_factory(
        group=time_span_group2,
        resource_state=State.CLOSED,
        weekdays=list(Weekday),
        full_day=True,
    )

    date_period3 = date_period_factory(
        name="Exceptions for december 24th and 25th",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=24),
        end_date=datetime.date(year=2020, month=12, day=25),
        override=True,
    )

    time_span_group3 = time_span_group_factory(period=date_period3)

    time_span_factory(
        group=time_span_group3,
        resource_state=State.EXIT_ONLY,
        weekdays=list(Weekday),
        full_day=True,
    )

    expected_time_element_closed = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=True,
    )

    expected_time_element_exit_only = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.EXIT_ONLY,
        override=True,
        full_day=True,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=12, day=23),
        datetime.date(year=2020, month=12, day=25),
    ) == {
        datetime.date(year=2020, month=12, day=23): [expected_time_element_closed],
        datetime.date(year=2020, month=12, day=24): [expected_time_element_exit_only],
        datetime.date(year=2020, month=12, day=25): [expected_time_element_exit_only],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_multiple_overrides(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        name="The whole year",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period2 = date_period_factory(
        name="Exception for december",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
        override=True,
    )

    time_span_group2 = time_span_group_factory(period=date_period2)

    time_span_factory(
        group=time_span_group2,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period3 = date_period_factory(
        name="Exceptions for december 24th and 25th",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=12, day=24),
        end_date=datetime.date(year=2020, month=12, day=25),
        override=True,
    )

    time_span_group3 = time_span_group_factory(period=date_period3)

    time_span_factory(
        group=time_span_group3,
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    expected_time_element_one_override = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=True,
        full_day=False,
    )

    expected_time_element_two_overrides = TimeElement(
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=True,
        full_day=False,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=12, day=23),
        datetime.date(year=2020, month=12, day=25),
    ) == {
        datetime.date(year=2020, month=12, day=23): [
            expected_time_element_one_override
        ],
        datetime.date(year=2020, month=12, day=24): [
            expected_time_element_two_overrides
        ],
        datetime.date(year=2020, month=12, day=25): [
            expected_time_element_two_overrides
        ],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_combine_full_day_with_non_full_day(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        name="The whole year",
        resource=resource,
        resource_state=State.UNDEFINED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
        override=False,
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
        weekdays=list(Weekday),
    )

    date_period_factory(
        name="Exception in december",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=12, day=3),
        end_date=datetime.date(year=2020, month=12, day=5),
        override=False,
    )

    expected_time_element_open = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    expected_time_element_open_24h = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=True,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=12, day=1),
        datetime.date(year=2020, month=12, day=8),
    ) == {
        datetime.date(year=2020, month=12, day=1): [expected_time_element_open],
        datetime.date(year=2020, month=12, day=2): [expected_time_element_open],
        datetime.date(year=2020, month=12, day=3): [expected_time_element_open_24h],
        datetime.date(year=2020, month=12, day=4): [expected_time_element_open_24h],
        datetime.date(year=2020, month=12, day=5): [expected_time_element_open_24h],
        datetime.date(year=2020, month=12, day=6): [expected_time_element_open],
        datetime.date(year=2020, month=12, day=7): [expected_time_element_open],
        datetime.date(year=2020, month=12, day=8): [expected_time_element_open],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_past_midnight(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=2, minute=0),
        end_time_on_next_day=True,
        weekdays=[Weekday.WEDNESDAY, Weekday.THURSDAY],
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=5, minute=0),
        end_time_on_next_day=True,
        weekdays=[Weekday.FRIDAY, Weekday.SATURDAY],
    )

    weekday_time_element_night = TimeElement(
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=2, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    weekday_time_element = TimeElement(
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=2, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    weekend_time_element_night = TimeElement(
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=5, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    weekend_time_element = TimeElement(
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=5, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=18),
    ) == {
        datetime.date(year=2020, month=10, day=14): [
            weekday_time_element,
        ],
        datetime.date(year=2020, month=10, day=15): [
            weekday_time_element_night,
            weekday_time_element,
        ],
        datetime.date(year=2020, month=10, day=16): [
            weekday_time_element_night,
            weekend_time_element,
        ],
        datetime.date(year=2020, month=10, day=17): [
            weekend_time_element_night,
            weekend_time_element,
        ],
    }


@pytest.mark.django_db
def test_resource_get_daily_opening_hours_past_midnight_combine(
    resource, date_period_factory, time_span_group_factory, time_span_factory
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=3, minute=0),
        end_time_on_next_day=True,
        weekdays=Weekday.business_days() + Weekday.weekend(),
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=2, minute=0),
        end_time=datetime.time(hour=9, minute=0),
        weekdays=Weekday.business_days() + Weekday.weekend(),
    )

    expected_time_element_morning = TimeElement(
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=9, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    expected_time_element_evening = TimeElement(
        start_time=datetime.time(hour=16, minute=0),
        end_time=datetime.time(hour=3, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert resource.get_daily_opening_hours(
        datetime.date(year=2020, month=10, day=12),
        datetime.date(year=2020, month=10, day=12),
    ) == {
        datetime.date(year=2020, month=10, day=12): [
            expected_time_element_morning,
            expected_time_element_evening,
        ],
    }
