import pytest
from hours import models
from rest_framework.exceptions import ValidationError


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

    