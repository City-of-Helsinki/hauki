import time
from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time

first_date = date(2020, 12, 31)
second_date = date(2022, 1, 1)
third_date = date(2022, 6, 30)


def assert_data_has_fields(data, fields):
    for field in fields:
        assert field in data
    assert len(data) == len(fields)


def assert_target_has_fields(target):
    fields = (
        "id",
        "data_source",
        "origin_id",
        "organization",
        "same_as",
        "target_type",
        "parent",
        "second_parent",
        "name",
        "address",
        "description",
        "created_time",
        "last_modified_time",
        "publication_time",
        "hours_updated",
        "identifiers",
        "links",
    )
    assert_data_has_fields(target, fields)


def assert_period_has_fields(period):
    fields = (
        "id",
        "data_source",
        "origin_id",
        "name",
        "description",
        "created_time",
        "last_modified_time",
        "publication_time",
        "openings",
        "target",
        "status",
        "override",
        "period",
    )
    assert_data_has_fields(period, fields)


def assert_daily_hours_has_fields(daily_hours):
    fields = ("target", "date", "opening")
    assert_data_has_fields(daily_hours, fields)


@pytest.mark.django_db
def test_get_target_list(
    api_client, django_assert_max_num_queries, targets, more_targets
):
    url = reverse("target-list")
    with django_assert_max_num_queries(4):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 20
    for target in response.data["results"]:
        assert_target_has_fields(target)


@pytest.mark.django_db
def test_filter_target_list(
    api_client, django_assert_max_num_queries, data_source, targets, more_targets
):
    url = reverse("target-list") + "?data_source=" + data_source.id
    with django_assert_max_num_queries(5):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 10
    for target in response.data["results"]:
        assert_target_has_fields(target)
        assert target["data_source"] == data_source.id


@pytest.mark.django_db
def test_get_target_detail(api_client, targets):
    url = reverse("target-detail", kwargs={"pk": targets[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_target_has_fields(response.data)


@pytest.mark.django_db
def test_get_period_list(api_client, django_assert_max_num_queries, periods):
    url = reverse("period-list")
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 50
    for period in response.data["results"]:
        assert_period_has_fields(period)


@pytest.mark.django_db
def test_filter_period_list(api_client, django_assert_max_num_queries, periods):
    url = reverse("period-list") + "?target=ds1:1"
    with django_assert_max_num_queries(4):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 5
    for period in response.data["results"]:
        assert_period_has_fields(period)
        assert reverse("target-detail", kwargs={"pk": "ds1:1"}) in period["target"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string", ("?start=today", "?start=-0d", "?start=" + str(second_date))
)
@freeze_time(second_date)
def test_start_filter_period_list(
    api_client, django_assert_max_num_queries, periods, input_string
):
    print(input_string)
    url = reverse("period-list") + input_string
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 20
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we only return ongoing and future periods
        assert (
            datetime.strptime(period["period"]["upper"], "%Y-%m-%d").date()
            >= second_date
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string", ("?end=today", "?end=-0d", "?end=" + str(first_date))
)
@freeze_time(first_date)
def test_end_filter_period_list(
    api_client, django_assert_max_num_queries, periods, input_string
):
    url = reverse("period-list") + input_string
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 10
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we only return ongoing and past periods
        assert (
            datetime.strptime(period["period"]["lower"], "%Y-%m-%d").date()
            <= first_date
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string",
    (
        "?start=today&end=" + str(third_date),
        "?start=" + str(second_date) + "&end=" + str(third_date),
    ),
)
@freeze_time(second_date)
def test_start_today_end_filter_period_list(
    api_client, django_assert_max_num_queries, periods, input_string
):
    url = reverse("period-list") + input_string
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 10
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for first part of 2022
        assert (
            datetime.strptime(period["period"]["upper"], "%Y-%m-%d").date()
            >= second_date
        )
        assert (
            datetime.strptime(period["period"]["lower"], "%Y-%m-%d").date()
            <= third_date
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string",
    (
        "?start=" + str(second_date) + "&end=today",
        "?start=" + str(second_date) + "&end=" + str(third_date),
    ),
)
@freeze_time(third_date)
def test_end_today_start_filter_period_list(
    api_client, django_assert_max_num_queries, periods, input_string
):
    url = reverse("period-list") + input_string
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == 10
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for first part of 2022
        assert (
            datetime.strptime(period["period"]["upper"], "%Y-%m-%d").date()
            >= second_date
        )
        assert (
            datetime.strptime(period["period"]["lower"], "%Y-%m-%d").date()
            <= third_date
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string", ("?start=today&end=today", "?start=-0d&end=+0d")
)
@freeze_time(first_date)
def test_get_periods_for_today(
    api_client, django_assert_max_num_queries, periods, input_string
):
    url = reverse("period-list") + input_string
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    # 31 Dec 2020 only has one period
    assert response.data["count"] == 10
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for today only
        assert (
            datetime.strptime(period["period"]["upper"], "%Y-%m-%d").date()
            >= first_date
        )
        assert (
            datetime.strptime(period["period"]["lower"], "%Y-%m-%d").date()
            <= first_date
        )


@pytest.mark.django_db
@freeze_time(first_date)
def test_get_periods_for_this_week(api_client, django_assert_max_num_queries, periods):
    url = reverse("period-list") + "?start=-0w&end=+0w"
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    # Week might extend into 2021
    assert response.data["count"] <= 20
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for the week only
        assert datetime.strptime(
            period["period"]["upper"], "%Y-%m-%d"
        ).date() >= first_date - timedelta(days=7)
        assert datetime.strptime(
            period["period"]["lower"], "%Y-%m-%d"
        ).date() <= first_date + timedelta(days=7)


@pytest.mark.django_db
@freeze_time(first_date)
def test_get_periods_for_this_month(api_client, django_assert_max_num_queries, periods):
    url = reverse("period-list") + "?start=-0m&end=+0m"
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    # December 2020 only has one period
    assert response.data["count"] == 10
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for the month only
        assert datetime.strptime(
            period["period"]["upper"], "%Y-%m-%d"
        ).date() >= first_date - timedelta(days=30)
        assert (
            datetime.strptime(period["period"]["lower"], "%Y-%m-%d").date()
            <= first_date
        )


@pytest.mark.django_db
@freeze_time(third_date)
def test_get_periods_for_this_year(api_client, django_assert_max_num_queries, periods):
    url = reverse("period-list") + "?start=-0y&end=+0y"
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    assert response.status_code == 200
    # 2022 has two periods
    assert response.data["count"] == 20
    for period in response.data["results"]:
        assert_period_has_fields(period)
        # check that we return periods for the year only
        assert datetime.strptime(
            period["period"]["upper"], "%Y-%m-%d"
        ).date() >= third_date - timedelta(days=181)
        assert datetime.strptime(
            period["period"]["lower"], "%Y-%m-%d"
        ).date() <= third_date + timedelta(days=184)


@pytest.mark.django_db
def test_get_period_detail(api_client, periods):
    url = reverse("period-detail", kwargs={"pk": periods[0].id})
    response = api_client.get(url)
    assert response.status_code == 200
    assert_period_has_fields(response.data)


@pytest.mark.django_db
@freeze_time(first_date)
def test_generate_get_and_filter_daily_hours_list(
    api_client, django_assert_max_num_queries, periods, openings
):
    # check generate performance
    start_time = time.process_time()
    for period in periods:
        period.update_daily_hours()
    print("daily hours generated")
    print(time.process_time() - start_time)
    assert time.process_time() - start_time < 25

    # check fetch performance
    start_time = time.process_time()
    url = reverse("dailyhours-list")
    with django_assert_max_num_queries(2):
        response = api_client.get(url)
    print("daily hours fetched")
    print(time.process_time() - start_time)
    assert time.process_time() - start_time < 0.05

    # check first 100 items
    assert response.status_code == 200
    assert response.data["count"] > 5000
    for daily_hours in response.data["results"]:
        assert_daily_hours_has_fields(daily_hours)

    # check target filter performance
    start_time = time.process_time()
    url = reverse("dailyhours-list") + "?target=ds1:1"
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    print("daily hours filtered")
    print(time.process_time() - start_time)
    assert time.process_time() - start_time < 0.02

    # check first 100 items
    assert response.status_code == 200
    assert response.data["count"] < 1500
    for daily_hours in response.data["results"]:
        assert_daily_hours_has_fields(daily_hours)
        assert reverse("target-detail", kwargs={"pk": "ds1:1"}) in daily_hours["target"]

    # check date filter performance
    start_time = time.process_time()
    url = reverse("dailyhours-list") + "?start=today&end=" + str(second_date)
    with django_assert_max_num_queries(3):
        response = api_client.get(url)
    print("daily hours filtered")
    print(time.process_time() - start_time)
    assert time.process_time() - start_time < 0.02

    # check first 100 items
    assert response.status_code == 200
    assert response.data["count"] < 4000
    for daily_hours in response.data["results"]:
        assert_daily_hours_has_fields(daily_hours)
        assert datetime.strptime(daily_hours["date"], "%Y-%m-%d").date() >= first_date
        assert datetime.strptime(daily_hours["date"], "%Y-%m-%d").date() <= second_date
