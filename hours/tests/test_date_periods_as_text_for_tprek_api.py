import datetime

import pytest
from django.urls import reverse
from freezegun import freeze_time


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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    with freeze_time("2020-10-17 12:00:00+02:00"):
        response = admin_client.get(
            url,
            content_type="application/json",
        )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data["results"]) == 1
