import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from freezegun import freeze_time

from hours.enums import State


@pytest.mark.django_db
def test_test_date_periods_as_text_for_tprek_api_with_hours(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    data_source = data_source_factory(id="tprek")

    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )
    time_span_group = time_span_group_factory(period=period)
    time_span_factory(group=time_span_group)

    url = reverse("date_periods_as_text_for_tprek-list")

    with freeze_time("2020-10-17 12:00:00+02:00"):
        response = admin_client.get(
            url,
            content_type="application/json",
        )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["resource"]["name"]["fi"] == resource.name_fi
    assert response.data["results"][0]["date_periods_as_text"]["fi"] != ""
    assert response.data["results"][0]["date_periods_as_text"]["sv"] != ""
    assert response.data["results"][0]["date_periods_as_text"]["en"] != ""


@pytest.mark.django_db
def test_test_date_periods_as_text_for_tprek_api_with_past_date_periods(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    django_assert_num_queries,
):
    data_source = data_source_factory(id="tprek")

    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    period1 = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2019, month=1, day=1),
        end_date=datetime.date(year=2019, month=12, day=31),
    )
    time_span_group = time_span_group_factory(period=period1)
    time_span_factory(group=time_span_group)

    period2 = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )
    time_span_group = time_span_group_factory(period=period2)
    time_span_factory(group=time_span_group)

    url = reverse("date_periods_as_text_for_tprek-list")

    with django_assert_num_queries(10):
        with freeze_time("2020-10-17 12:00:00+02:00"):
            response = admin_client.get(
                url,
                content_type="application/json",
            )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data["results"]) == 1


def _create_period_with_group_and_rule(
    resource,
    date_period_factory,
    *,
    start_date,
    end_date,
    period_name="Test period",
    period_description="A description that was previously deferred",
):
    return date_period_factory(
        resource=resource,
        name=period_name,
        description=period_description,
        resource_state=State.OPEN,
        start_date=start_date,
        end_date=end_date,
    )


@pytest.mark.django_db
def test_opening_hours_viewset_constant_query_count(
    admin_client,
    resource,
    date_period_factory,
):
    """Query count for OpeningHoursViewSet must stay constant regardless of how
    many DatePeriods the resource has."""
    today = datetime.date(2024, 6, 3)
    url = reverse("opening_hours-list")
    params = {
        "start_date": str(today),
        "end_date": str(today + datetime.timedelta(days=6)),
    }

    _create_period_with_group_and_rule(
        resource,
        date_period_factory,
        start_date=today,
        end_date=today + datetime.timedelta(days=30),
    )

    with freeze_time("2024-06-03 12:00:00+02:00"):
        with CaptureQueriesContext(connection) as ctx_1:
            resp1 = admin_client.get(url, params)
    assert resp1.status_code == 200, resp1.data
    count_1 = len(ctx_1.captured_queries)

    # Add two more date periods — same date range so they also overlap the
    # query window and force deferred-field access in get_daily_opening_hours()
    for i in range(2):
        _create_period_with_group_and_rule(
            resource,
            date_period_factory,
            start_date=today,
            end_date=today + datetime.timedelta(days=30),
            period_name=f"Extra period {i}",
            period_description=f"Extra description {i}",
        )

    with freeze_time("2024-06-03 12:00:00+02:00"):
        with CaptureQueriesContext(connection) as ctx_3:
            resp3 = admin_client.get(url, params)
    assert resp3.status_code == 200, resp3.data
    count_3 = len(ctx_3.captured_queries)

    assert count_1 == count_3, (
        f"N+1 detected: {count_3} queries for 3 date periods vs "
        f"{count_1} query for 1 date period."
    )
