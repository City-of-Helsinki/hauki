import pytest
from django.urls import reverse


def assert_data_has_fields(data, fields):
    for field in fields:
        assert field in data
    assert len(data) == len(fields)

def assert_target_has_fields(target):
    fields = (
        'id',
        'data_source',
        'origin_id',
        'same_as',
        'target_type',
        'parent',
        'second_parent',
        'name',
        'description',
        'created_time',
        'last_modified_time',
        'publication_time',
        'hours_updated'
        )
    assert_data_has_fields(target, fields)

def assert_period_has_fields(period):
    fields = (
        'id',
        'data_source',
        'origin_id',
        'name',
        'description',
        'created_time',
        'last_modified_time',
        'publication_time',
        'openings',
        'target',
        'status',
        'override',
        'period'
        )
    assert_data_has_fields(period, fields)

def assert_daily_hours_has_fields(daily_hours):
    fields = (
        'target',
        'date',
        'opening'
        )
    assert_data_has_fields(daily_hours, fields)

@pytest.mark.django_db
def test_get_target_list(api_client, targets):
    url = reverse('target-list')
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 10
    for target in response.data:
        assert_target_has_fields(target)

@pytest.mark.django_db
def test_get_target_detail(api_client, targets):
    url = reverse('target-detail', kwargs={'pk': targets[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_target_has_fields(response.data)

@pytest.mark.django_db
def test_get_period_list(api_client, periods):
    url = reverse('period-list')
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 40
    for period in response.data:
        assert_period_has_fields(period)

@pytest.mark.django_db
def test_get_period_detail(api_client, periods):
    url = reverse('period-detail', kwargs={'pk': periods[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_period_has_fields(response.data)
