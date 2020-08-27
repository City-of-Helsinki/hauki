import pytest
import time
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
        'organization',
        'same_as',
        'target_type',
        'parent',
        'second_parent',
        'name',
        'description',
        'created_time',
        'last_modified_time',
        'publication_time',
        'hours_updated',
        'identifiers'
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
def test_get_target_list(api_client, django_assert_max_num_queries, targets):
    url = reverse('target-list')
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data['count'] == 10
    for target in response.data['results']:
        assert_target_has_fields(target)

@pytest.mark.django_db
def test_get_target_detail(api_client, targets):
    url = reverse('target-detail', kwargs={'pk': targets[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_target_has_fields(response.data)

@pytest.mark.django_db
def test_get_period_list(api_client, django_assert_max_num_queries, periods):
    url = reverse('period-list')
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data['count'] == 40
    for period in response.data['results']:
        assert_period_has_fields(period)

@pytest.mark.django_db
def test_get_period_detail(api_client, periods):
    url = reverse('period-detail', kwargs={'pk': periods[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_period_has_fields(response.data)

def test_generate_and_get_daily_hours_list(api_client, django_assert_max_num_queries, periods, openings):
    # check generate performance
    start_time = time.process_time()
    for period in periods:
        period.update_daily_hours()
    print('daily hours generated')
    print(time.process_time() - start_time)
    assert (time.process_time() - start_time < 25)

    # check fetch performance
    start_time = time.process_time()
    url = reverse('dailyhours-list')
    with django_assert_max_num_queries(2):
        response = api_client.get(url)
    print('daily hours fetched')
    print(time.process_time() - start_time)
    assert (time.process_time() - start_time < 0.05)

    # check data
    assert response.status_code == 200
    assert response.data['count'] > 100
    for daily_hours in response.data['results']:
        assert_daily_hours_has_fields(daily_hours)
