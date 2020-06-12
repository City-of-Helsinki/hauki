import pytest
from hours import models
from hours.models import DataSource, Opening
from rest_framework.exceptions import ValidationError
from datetime import date, timedelta


@pytest.mark.parametrize('klass', ('Target', 'Keyword'))
@pytest.mark.django_db
def test_base_model(klass, data_source):
    Klass = getattr(models, klass)
    with pytest.raises(DataSource.DoesNotExist):
        Klass.objects.create(data_source_id='not there')
    with pytest.raises(DataSource.DoesNotExist):
        Klass.objects.create(data_source_id='not there', origin_id='1')
    with pytest.raises(DataSource.DoesNotExist):
        Klass.objects.create(origin_id='1')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1', origin_id='1', id='something else')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1', origin_id='1', id='ds2:2')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1', origin_id=1)
    Klass.objects.create(data_source_id='ds1', origin_id='1')


@pytest.mark.django_db
def test_get_period_for_date(target, short_period, medium_period, long_period):
    target = target('1')
    target.save()
    short_period = short_period(target, '1')
    short_period.save()
    medium_period = medium_period(target, '2')
    medium_period.save()
    long_period = long_period(target, '3')
    long_period.save()
    test_date = date(2021,7,15)
    assert short_period == target.get_periods_for_range(test_date)[test_date]


@pytest.mark.django_db
def test_get_override_period_for_date(target, short_period, medium_period, long_period):
    target = target('1')
    target.save()
    short_period = short_period(target, '1')
    short_period.save()
    medium_period = medium_period(target, '2')
    medium_period.override = True
    medium_period.save()
    long_period = long_period(target, '3')
    long_period.save()
    test_date = date(2021,7,15)
    assert medium_period == target.get_periods_for_range(test_date)[test_date]


@pytest.mark.django_db
def test_get_weekly_openings_for_range(target, long_period, period_first_week_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    period_opening = period_first_week_opening(long_period, date(2021,7,1).isoweekday())
    period_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert period_opening in openings[date(2021,7,1)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert not openings[date(2021,7,2)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,2))
    assert period_opening in openings[date(2021,7,8)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert not openings[date(2021,7,9)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,9))
    assert period_opening in openings[date(2021,7,15)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,15))
    assert not openings[date(2021,7,16)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,16))
    assert period_opening in openings[date(2021,7,22)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,22))
    assert not openings[date(2021,7,23)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,23))
    assert period_opening in openings[date(2021,7,29)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,29))
    assert not openings[date(2021,7,30)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,30))


@pytest.mark.django_db
def test_get_multiple_openings_for_date(target, long_period, period_first_week_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    first_opening = period_first_week_opening(long_period, date(2021,7,1).isoweekday())
    first_opening.save()
    second_opening = period_first_week_opening(long_period, date(2021,7,1).isoweekday())
    second_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert first_opening in openings[date(2021,7,1)]
    assert first_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert second_opening in openings[date(2021,7,1)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert not openings[date(2021,7,2)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,2))
    assert first_opening in openings[date(2021,7,8)]
    assert first_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert second_opening in openings[date(2021,7,8)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert not openings[date(2021,7,9)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,9))


@pytest.mark.django_db
def test_get_two_weekly_openings_for_range(target, long_period, period_first_week_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    period_opening = period_first_week_opening(long_period, date(2021,7,1).isoweekday())
    period_opening.save()
    second_opening = period_first_week_opening(long_period,  date(2021,7,6).isoweekday())
    second_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert period_opening in openings[date(2021,7,1)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert not openings[date(2021,7,2)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,2))
    assert second_opening in openings[date(2021,7,6)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,6))
    assert period_opening in openings[date(2021,7,8)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert not openings[date(2021,7,9)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,9))
    assert second_opening in openings[date(2021,7,13)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,13))
    assert period_opening in openings[date(2021,7,15)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,15))
    assert not openings[date(2021,7,16)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,16))
    assert second_opening in openings[date(2021,7,20)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,20))
    assert period_opening in openings[date(2021,7,22)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,22))
    assert not openings[date(2021,7,23)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,23))
    assert second_opening in openings[date(2021,7,27)]
    assert second_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,27))
    assert period_opening in openings[date(2021,7,29)]
    assert period_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,29))
    assert not openings[date(2021,7,30)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,30))


@pytest.mark.django_db
def test_get_biweekly_openings_for_range(target, long_period, period_first_week_opening, period_second_week_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    first_week_opening = period_first_week_opening(long_period, long_period.period.lower.isoweekday())
    second_week_opening = period_second_week_opening(long_period, long_period.period.lower.isoweekday())
    first_week_opening.save()
    second_week_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert first_week_opening in openings[long_period.period.lower]
    assert first_week_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower)
    assert not openings[long_period.period.lower + timedelta(days=1)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=1))
    assert second_week_opening in openings[long_period.period.lower + timedelta(days=7)]
    assert second_week_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=7))
    assert not openings[long_period.period.lower + timedelta(days=8)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=8))
    assert first_week_opening in openings[long_period.period.lower + timedelta(days=14)]
    assert first_week_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=14))
    assert not openings[long_period.period.lower + timedelta(days=15)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=15))


@pytest.mark.django_db
def test_get_biweekly_opening_for_range(target, long_period, period_first_week_opening, period_second_week_closing):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    first_week_opening = period_first_week_opening(long_period, long_period.period.lower.isoweekday())
    second_week_closing = period_second_week_closing(long_period, long_period.period.lower.isoweekday())
    first_week_opening.save()
    second_week_closing.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert first_week_opening in openings[long_period.period.lower]
    assert first_week_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower)
    assert not openings[long_period.period.lower + timedelta(days=1)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=1))
    assert second_week_closing in openings[long_period.period.lower + timedelta(days=7)]
    assert second_week_closing in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=7))
    assert not openings[long_period.period.lower + timedelta(days=8)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=8))
    assert first_week_opening in openings[long_period.period.lower + timedelta(days=14)]
    assert first_week_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=14))
    assert not openings[long_period.period.lower + timedelta(days=15)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=long_period.period.lower + timedelta(days=15))


@pytest.mark.django_db
def test_get_monthly_openings_for_range(target, long_period, period_monthly_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    monthly_opening = period_monthly_opening(long_period, date(2021,7,1).isoweekday())
    monthly_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert monthly_opening in openings[date(2021,7,1)]
    assert monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert not openings[date(2021,7,8)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert not openings[date(2021,7,15)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,15))
    assert not openings[date(2021,7,22)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,22))
    assert not openings[date(2021,7,29)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,29))
    assert monthly_opening in openings[date(2021,8,5)]
    assert monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,8,5))


@pytest.mark.django_db
def test_get_two_monthly_openings_for_date(target, long_period, period_monthly_opening, period_second_monthly_opening):
    target = target('1')
    target.save()
    long_period = long_period(target, '1')
    long_period.save()
    monthly_opening = period_monthly_opening(long_period, date(2021,7,1).isoweekday())
    monthly_opening.save()
    second_monthly_opening = period_second_monthly_opening(long_period, date(2021,7,1).isoweekday())
    second_monthly_opening.save()
    openings = target.get_openings_for_range(long_period.period.lower, long_period.period.upper)
    assert monthly_opening in openings[date(2021,7,1)]
    assert monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,1))
    assert not openings[date(2021,7,8)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,8))
    assert second_monthly_opening in openings[date(2021,7,15)]
    assert second_monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,15))
    assert not openings[date(2021,7,22)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,22))
    assert not openings[date(2021,7,29)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,29))
    assert monthly_opening in openings[date(2021,8,5)]
    assert monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,8,5))
    assert not openings[date(2021,8,12)]
    assert not Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,7,12))
    assert second_monthly_opening in openings[date(2021,8,19)]
    assert second_monthly_opening in Opening.objects.filter(daily_hours__target=target,daily_hours__date=date(2021,8,19))
