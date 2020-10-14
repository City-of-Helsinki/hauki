import datetime

import pytest

from hours.enums import FrequencyModifier, PeriodType, RuleContext, RuleSubject, Weekday
from hours.models import TimeElement


@pytest.mark.django_db
def test_resource_get_daily_opening_hours(
    resource, date_period_factory, opening_hours_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    opening_hours_factory(
        period=date_period,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.business_days(),
    )

    opening_hours_factory(
        period=date_period,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        weekdays=Weekday.weekend(),
    )

    weekday_time_element = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        period_type=PeriodType.OPEN,
        override=False,
        full_day=False,
    )

    weekend_time_element = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        period_type=PeriodType.OPEN,
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
def test_get_period_for_date(resource, date_period_factory, opening_hours_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    opening_hours_factory(
        period=date_period,
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
                period_type=PeriodType.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }


@pytest.mark.django_db
def test_get_period_for_date_with_rule(
    resource, date_period_factory, opening_hours_factory, rule_factory
):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    opening_hours_factory(
        period=date_period,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=18, minute=0),
        weekdays=Weekday.business_days(),
    )

    opening_hours_factory(
        period=date_period,
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.weekend(),
    )

    rule_factory(
        period=date_period,
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
                period_type=PeriodType.OPEN,
                override=False,
                full_day=False,
            )
        ]
    }


@pytest.mark.django_db
def test_rule_filter_dates1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates1_2(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates1_3(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates2(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates3(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates4(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates5(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates6(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates6_1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates6_2(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
        context=RuleContext.PERIOD,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates7(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates7_1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=9, day=1),
        end_date=datetime.date(year=2020, month=11, day=30),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates8(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates8_1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates9(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule1 = rule_factory(
        period=date_period,
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
def test_rule_filter_dates10(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule1 = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        start=1,
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
def test_rule_filter_dates10_1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule1 = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.WEEK,
        start=1,
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
def test_rule_filter_dates11(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates11_1(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
def test_rule_filter_dates11_2(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2019, month=1, day=1)
    end_date = datetime.date(year=2021, month=12, day=31)

    days_in_march = {datetime.date(year=2020, month=3, day=d) for d in range(1, 32)}

    assert rule.apply_to_date_range(start_date, end_date) == days_in_march


@pytest.mark.django_db
def test_rule_filter_dates11_3(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=5, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=15)
    end_date = datetime.date(year=2020, month=4, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == set()


@pytest.mark.django_db
def test_rule_filter_dates11_4(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=1, day=31),
    )

    rule = rule_factory(
        period=date_period,
        context=RuleContext.YEAR,
        subject=RuleSubject.MONTH,
        start=3,
    )

    start_date = datetime.date(year=2020, month=2, day=1)
    end_date = datetime.date(year=2020, month=4, day=30)

    assert rule.apply_to_date_range(start_date, end_date) == set()


@pytest.mark.django_db
def test_rule_filter_dates12(resource, date_period_factory, rule_factory):
    date_period = date_period_factory(
        resource=resource,
        period_type=PeriodType.OPEN,
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2021, month=12, day=31),
    )

    rule = rule_factory(
        period=date_period,
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
