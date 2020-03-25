import pytest
from hours import models
from rest_framework.exceptions import ValidationError
from datetime import date


@pytest.mark.parametrize('klass', ('Target', 'Keyword'))
@pytest.mark.django_db
def test_base_model(klass, data_source):
    Klass = getattr(models, klass)
    with pytest.raises(models.DataSource.DoesNotExist):
        Klass.objects.create(data_source_id='not there')
    with pytest.raises(models.DataSource.DoesNotExist):
        Klass.objects.create(data_source_id='not there', origin_id='1')
    with pytest.raises(models.DataSource.DoesNotExist):
        Klass.objects.create(origin_id='1')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1', origin_id='1', id='something else')
    with pytest.raises(ValidationError):
        Klass.objects.create(data_source_id='ds1', origin_id='1', id='ds2:2')
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
    assert short_period == target.get_period_for_date(date(2021,7,15))


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
    assert medium_period == target.get_period_for_date(date(2021,7,15))