import datetime
import json
from unittest.mock import patch

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from rest_framework.exceptions import ValidationError as DRFValidationError

from hours.enums import RuleContext, RuleSubject, State, Weekday
from hours.models import DatePeriod, PeriodOrigin, TimeSpanGroup
from hours.tests.utils import assert_response_status_code


@pytest.mark.django_db
def test_invalid_format_returns_400(admin_client):
    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2030-101-01"})

    assert response.status_code == 400, f"{response.status_code} {response.data}"
    assert response.data["start_date_lte"][0] == "Invalid date format"


@pytest.mark.django_db
def test_list_date_periods_empty(admin_client):
    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2030-01-01"})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 0


@pytest.mark.django_db
def test_list_date_periods_one_date_period(admin_client, resource, date_period_factory):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=None,
    )

    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2030-01-01"})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 1
    assert response.data[0]["id"] == date_period.id


@pytest.mark.django_db
def test_list_date_periods_multiple_date_periods(
    admin_client, resource, date_period_factory
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=None,
    )
    date_period2 = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=None,
        end_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2030-01-01"})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 2
    assert response.data[0]["id"] == date_period.id
    period_ids = {i["id"] for i in response.data}

    assert period_ids == {date_period.id, date_period2.id}


@pytest.mark.django_db
def test_list_date_periods_filter_by_resource(
    admin_client, resource_factory, date_period_factory
):
    resource = resource_factory()
    resource2 = resource_factory()
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=None,
    )
    date_period_factory(
        resource=resource2,
        name="Testperiod",
        start_date=None,
        end_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(url, data={"resource": resource.id})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 1
    assert response.data[0]["id"] == date_period.id


@pytest.mark.django_db
def test_list_date_periods_filter_by_data_source(
    admin_client, resource, data_source_factory, date_period_factory
):
    expected_data_source = data_source_factory()
    expected_date_period = date_period_factory(
        resource=resource,
        data_sources=[expected_data_source],
    )
    date_period_factory(
        resource=resource,
        data_sources=[data_source_factory()],
    )

    url = reverse("date_period-list")

    response = admin_client.get(
        url, data={"resource": resource.id, "data_source": [expected_data_source.id]}
    )

    assert_response_status_code(response, 200)
    assert len(response.data) == 1
    assert response.data[0]["id"] == expected_date_period.id


@pytest.mark.django_db
def test_list_date_periods_filter_by_multiple_data_sources(
    admin_client, resource, data_source_factory, date_period_factory
):
    data_source_1 = data_source_factory()
    data_source_2 = data_source_factory()

    date_period_1 = date_period_factory(
        resource=resource,
        data_sources=[data_source_1],
    )

    date_period_2 = date_period_factory(
        resource=resource,
        data_sources=[data_source_2],
    )

    date_period_factory(
        resource=resource,
        data_sources=[data_source_factory()],
    )

    url = reverse("date_period-list")

    response = admin_client.get(
        url,
        data={
            "resource": resource.id,
            "data_source": f"{data_source_1.id},{data_source_2.id}",
        },
    )

    assert_response_status_code(response, 200)
    assert len(response.data) == 2
    returned_ids = [item["id"] for item in response.data]
    assert date_period_1.id in returned_ids
    assert date_period_2.id in returned_ids


@pytest.mark.django_db
def test_list_date_periods_filter_by_resource_direct_data_source(
    admin_client, resource, data_source_factory, date_period_factory, resource_factory
):
    expected_data_source = data_source_factory()
    resource.data_sources.add(expected_data_source)
    expected_date_period = date_period_factory(
        resource=resource,
    )
    date_period_factory(
        resource=resource_factory(),
        start_date=datetime.date(year=2024, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(
        url,
        data={
            "resource_data_source": expected_data_source.id,
            "start_date_lte": "2024-01-05",
        },
    )

    assert_response_status_code(response, 200)
    assert len(response.data) == 1
    assert response.data[0]["id"] == expected_date_period.id


@pytest.mark.django_db
def test_list_date_periods_filter_by_resource_data_source_ancestor(
    admin_client,
    resource,
    data_source_factory,
    date_period_factory,
    resource_factory,
    resource_origin_factory,
):
    expected_data_source = data_source_factory()
    resource.data_sources.add(expected_data_source)
    child_resource = resource_factory()
    child_resource.parents.add(resource)
    resource.save()

    expected_date_period = date_period_factory(
        resource=resource,
        start_date=datetime.date(year=2024, month=1, day=1),
        end_date=datetime.date(year=2024, month=5, day=31),
    )
    child_date_period = date_period_factory(
        resource=child_resource,
        start_date=datetime.date(year=2024, month=1, day=1),
        end_date=datetime.date(year=2024, month=5, day=31),
    )
    date_period_factory(
        resource=resource_factory(),
        start_date=datetime.date(year=2024, month=1, day=1),
        end_date=datetime.date(year=2024, month=5, day=31),
    )

    url = reverse("date_period-list")

    response = admin_client.get(
        url,
        data={
            "resource_data_source": expected_data_source.id,
            "start_date_gte": "2024-01-01",
        },
    )

    assert_response_status_code(response, 200)
    assert len(response.data) == 2
    returned_ids = [item["id"] for item in response.data]
    assert expected_date_period.id in returned_ids
    assert child_date_period.id in returned_ids


@pytest.mark.django_db
def test_list_date_periods_filter_by_multiple_resource_data_sources(
    admin_client,
    resource,
    data_source_factory,
    date_period_factory,
    resource_factory,
):
    data_source_1 = data_source_factory()
    data_source_2 = data_source_factory()

    resource_1 = resource
    resource_1.data_sources.add(data_source_1)
    date_period_1 = date_period_factory(
        resource=resource_1,
        start_date=datetime.date(year=2024, month=1, day=1),
    )

    resource_2 = resource_factory()
    resource_2.data_sources.add(data_source_2)
    date_period_2 = date_period_factory(
        resource=resource_2,
        start_date=datetime.date(year=2024, month=1, day=1),
    )

    resource_3 = resource_factory()
    resource_3.data_sources.add(data_source_factory())
    date_period_factory(
        resource=resource_3,
        start_date=datetime.date(year=2024, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(
        url,
        data={
            "resource_data_source": f"{data_source_1.id},{data_source_2.id}",
            "start_date": "2024-01-01",
        },
    )

    assert_response_status_code(response, 200)
    assert len(response.data) == 2
    returned_ids = [item["id"] for item in response.data]
    assert date_period_1.id in returned_ids
    assert date_period_2.id in returned_ids


@pytest.mark.django_db
def test_list_date_periods_filter_start_date_lte(
    admin_client, resource, date_period_factory
):
    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=None,
    )
    date_period2 = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=None,
        end_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2019-01-01"})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 1
    assert response.data[0]["id"] == date_period2.id


@pytest.mark.django_db
def test_list_date_periods_filter_end_date_gte(
    admin_client, resource, date_period_factory
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=None,
    )
    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=None,
        end_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-list")

    response = admin_client.get(url, data={"end_date_gte": "2021-01-01"})

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    assert len(response.data) == 1
    assert response.data[0]["id"] == date_period.id


@pytest.mark.django_db
def test_create_date_period_no_time_span_groups(resource, admin_client):
    url = reverse("date_period-list")

    data = {
        "resource": resource.id,
        "name": "Testperiod",
        "description": "Testperiod desc",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "resource_state": "undefined",
        "override": "false",
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.start_date == datetime.date(year=2020, month=1, day=1)
    assert date_period.time_span_groups.count() == 0


@pytest.mark.django_db
def test_create_date_period_one_time_span_group_one_time_span(resource, admin_client):
    url = reverse("date_period-list")

    data = {
        "resource": resource.id,
        "name": "Testperiod",
        "description": "Testperiod desc",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "resource_state": "undefined",
        "override": "false",
        "time_span_groups": [
            {
                "time_spans": [
                    {
                        "full_day": True,
                        "resource_state": "closed",
                    }
                ]
            }
        ],
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.start_date == datetime.date(year=2020, month=1, day=1)
    assert date_period.time_span_groups.count() == 1

    time_span_group = date_period.time_span_groups.first()
    assert time_span_group.time_spans.count() == 1
    assert time_span_group.rules.count() == 0

    time_span = time_span_group.time_spans.first()
    assert time_span.start_time is None
    assert time_span.end_time is None
    assert time_span.full_day is True
    assert time_span.resource_state == State.CLOSED


@pytest.mark.django_db
def test_create_date_period_one_time_span_group_one_time_span_one_rule(
    resource, admin_client
):
    url = reverse("date_period-list")

    data = {
        "resource": resource.id,
        "name": "Testperiod",
        "description": "Testperiod desc",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "resource_state": "undefined",
        "override": "false",
        "time_span_groups": [
            {
                "time_spans": [
                    {
                        "full_day": True,
                        "resource_state": "closed",
                    }
                ],
                "rules": [
                    {
                        "context": "period",
                        "subject": "week",
                        "start": 1,
                    }
                ],
            }
        ],
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.start_date == datetime.date(year=2020, month=1, day=1)
    assert date_period.time_span_groups.count() == 1

    time_span_group = date_period.time_span_groups.first()
    assert time_span_group.time_spans.count() == 1
    assert time_span_group.rules.count() == 1

    time_span = time_span_group.time_spans.first()
    assert time_span.start_time is None
    assert time_span.end_time is None
    assert time_span.full_day is True
    assert time_span.resource_state == State.CLOSED

    rule = time_span_group.rules.first()
    assert rule.context == RuleContext.PERIOD
    assert rule.subject == RuleSubject.WEEK
    assert rule.start == 1


@pytest.mark.django_db
def test_update_date_period_no_time_span_groups(
    resource, date_period_factory, admin_client
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})

    data = {
        "id": date_period.id,
        "name": "Testperiod edit",
        "description": "Testperiod desc",
        "start_date": "2020-02-02",
        "end_date": "2020-11-30",
    }

    response = admin_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.name == "Testperiod edit"
    assert date_period.start_date == datetime.date(year=2020, month=2, day=2)
    assert date_period.time_span_groups.count() == 0


@pytest.mark.django_db
def test_update_date_period_keep_one_time_span(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    admin_client,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
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

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})

    data = {
        "id": date_period.id,
        "name": "Testperiod edit",
        "description": "Testperiod desc",
        "start_date": "2020-02-02",
        "end_date": "2020-11-30",
    }

    response = admin_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.name == "Testperiod edit"
    assert date_period.start_date == datetime.date(year=2020, month=2, day=2)
    assert date_period.time_span_groups.count() == 1
    assert time_span_group.time_spans.count() == 1

    time_span = time_span_group.time_spans.first()
    assert time_span.start_time == datetime.time(hour=8, minute=0)
    assert time_span.end_time == datetime.time(hour=16, minute=0)


@pytest.mark.django_db
def test_update_date_period_add_one_time_span(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    admin_client,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span = time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.business_days(),
    )

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})

    data = {
        "id": date_period.id,
        "name": "Testperiod edit",
        "description": "Testperiod desc",
        "start_date": "2020-02-02",
        "end_date": "2020-11-30",
        "time_span_groups": [
            {
                "id": time_span_group.id,
                "time_spans": [
                    {"id": time_span.id},
                    {
                        "full_day": True,
                        "resource_state": "closed",
                    },
                ],
            }
        ],
    }

    response = admin_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])

    assert date_period.resource == resource
    assert date_period.name == "Testperiod edit"
    assert date_period.start_date == datetime.date(year=2020, month=2, day=2)
    assert date_period.time_span_groups.count() == 1
    assert time_span_group.time_spans.count() == 2

    existing_time_span = time_span_group.time_spans.get(pk=time_span.id)
    assert existing_time_span.start_time == datetime.time(hour=8, minute=0)
    assert existing_time_span.end_time == datetime.time(hour=16, minute=0)

    new_time_span = time_span_group.time_spans.exclude(pk=time_span.id).first()
    assert new_time_span.full_day is True
    assert new_time_span.resource_state == State.CLOSED


@pytest.mark.django_db
def test_create_time_span_no_group(admin_client):
    url = reverse("time_span-list")

    data = {
        "full_day": True,
        "resource_state": "closed",
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, f"{response.status_code} {response.data}"

    assert "group" in response.data
    assert response.data["group"][0].code == "required"


@pytest.mark.django_db
def test_create_time_span_with_group(
    admin_client, resource, date_period_factory, time_span_group_factory
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    url = reverse("time_span-list")

    data = {
        "group": time_span_group.id,
        "full_day": True,
        "resource_state": "closed",
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"


@pytest.mark.django_db
def test_date_period_order_field_in_response(
    admin_client, resource, date_period_factory
):
    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        order=5,
    )

    url = reverse("date_period-list")
    response = admin_client.get(url, data={"resource": resource.id})

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert len(response.data) == 1
    assert response.data[0]["order"] == 5


@pytest.mark.django_db
def test_date_period_order_field_null_by_default(
    admin_client, resource, date_period_factory
):
    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-list")
    response = admin_client.get(url, data={"resource": resource.id})

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert len(response.data) == 1
    assert response.data[0]["order"] is None


@pytest.mark.django_db
def test_create_date_period_with_order(admin_client, resource):
    url = reverse("date_period-list")

    data = {
        "resource": resource.id,
        "name": "Ordered period",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "resource_state": "undefined",
        "override": False,
        "order": 3,
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"
    assert response.data["order"] == 3

    date_period = DatePeriod.objects.get(pk=response.data["id"])
    assert date_period.order == 3


@pytest.mark.django_db
def test_update_date_period_order(admin_client, resource, date_period_factory):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
    )

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})

    response = admin_client.patch(
        url,
        data=json.dumps({"order": 10}, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert response.data["order"] == 10

    date_period.refresh_from_db()
    assert date_period.order == 10


@pytest.mark.django_db
def test_date_periods_ordered_by_order_field_before_start_date(
    admin_client, resource, date_period_factory
):
    dp_no_order_early = date_period_factory(
        resource=resource,
        name="No order, early start",
        start_date=datetime.date(year=2020, month=1, day=1),
    )
    dp_order_2 = date_period_factory(
        resource=resource,
        name="Order 2",
        start_date=datetime.date(year=2021, month=1, day=1),
        order=2,
    )

    dp_order_1 = date_period_factory(
        resource=resource,
        name="Order 1",
        start_date=datetime.date(year=2022, month=1, day=1),
        order=1,
    )

    dp_no_order_late = date_period_factory(
        resource=resource,
        name="No order, late start",
        start_date=datetime.date(year=2023, month=1, day=1),
    )

    url = reverse("date_period-list")
    response = admin_client.get(url, data={"resource": resource.id})

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert len(response.data) == 4

    returned_ids = [item["id"] for item in response.data]

    # Periods with an explicit order come first (ascending by order),
    # then periods without an order, sorted by start_date.
    assert returned_ids.index(dp_order_1.id) < returned_ids.index(dp_order_2.id)
    assert returned_ids.index(dp_order_2.id) < returned_ids.index(dp_no_order_early.id)
    assert returned_ids.index(dp_no_order_early.id) < returned_ids.index(
        dp_no_order_late.id
    )


@pytest.mark.django_db
def test_date_periods_api_ordering_by_order_field(
    admin_client, resource, date_period_factory
):
    dp_b = date_period_factory(
        resource=resource,
        name="Order 2",
        start_date=datetime.date(year=2020, month=6, day=1),
        order=2,
    )

    dp_a = date_period_factory(
        resource=resource,
        name="Order 1",
        start_date=datetime.date(year=2020, month=6, day=1),
        order=1,
    )

    url = reverse("date_period-list")
    response = admin_client.get(
        url, data={"resource": resource.id, "ordering": "order"}
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert len(response.data) == 2
    assert response.data[0]["id"] == dp_a.id
    assert response.data[1]["id"] == dp_b.id


@pytest.mark.django_db
def test_date_periods_api_ordering_by_order_field_with_nulls(
    admin_client, resource, date_period_factory
):
    dp_no_order_early = date_period_factory(
        resource=resource,
        name="No order, early start",
        start_date=datetime.date(year=2020, month=1, day=1),
    )

    dp_order_2 = date_period_factory(
        resource=resource,
        name="Order 2",
        start_date=datetime.date(year=2021, month=1, day=1),
        order=2,
    )

    dp_order_1 = date_period_factory(
        resource=resource,
        name="Order 1",
        start_date=datetime.date(year=2022, month=1, day=1),
        order=1,
    )

    dp_no_order_late = date_period_factory(
        resource=resource,
        name="No order, late start",
        start_date=datetime.date(year=2023, month=1, day=1),
    )

    url = reverse("date_period-list")
    response = admin_client.get(
        url, data={"resource": resource.id, "ordering": "order"}
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"
    assert len(response.data) == 4

    returned_ids = [item["id"] for item in response.data]

    # Periods with an explicit order come first (ascending by order),
    # then periods without an order, sorted by start_date.
    assert returned_ids.index(dp_order_1.id) < returned_ids.index(dp_order_2.id)
    assert returned_ids.index(dp_order_2.id) < returned_ids.index(dp_no_order_early.id)
    assert returned_ids.index(dp_no_order_early.id) < returned_ids.index(
        dp_no_order_late.id
    )


@pytest.mark.django_db
def test_put_rolls_back_time_span_group_creation_on_origin_write_failure(
    resource,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    date_period_factory,
    api_client,
):
    """PUT that creates a new time_span_group but then fails during origin save
    must be fully rolled back — the new time_span_group must not be persisted.

    super().update_or_create_reverse_relations() creates/updates time_span_groups
    *before* our code processes origins.  Without transaction.atomic() in the
    viewset, the TimeSpanGroup INSERT is already committed when the origin write
    raises, leaving the period in a partial / inconsistent state.
    """
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    # Period deliberately starts with no time_span_groups.
    date_period = date_period_factory(resource=resource, name="Period")
    tsg_count_before = TimeSpanGroup.objects.count()

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})
    data = {
        "resource": resource.id,
        "name": "Period",
        "start_date": None,
        "end_date": None,
        "resource_state": "undefined",
        "override": False,
        # NEW group — super().update_or_create_reverse_relations() will INSERT
        # this into the DB before origins are processed.
        "time_span_groups": [{"time_spans": [], "rules": []}],
        # Valid origin whose save() is mocked to fail, simulating any
        # DB-level failure that occurs after time_span_groups are written.
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "new-origin",
            }
        ],
    }

    def failing_save(*args, **kwargs):
        raise DRFValidationError({"origin_id": ["Simulated DB failure"]})

    with patch("hours.serializers.PeriodOriginSerializer.save", failing_save):
        response = api_client.put(
            url,
            data=json.dumps(data, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    assert response.status_code == 400, f"{response.status_code} {response.data}"

    # With transaction.atomic() the TimeSpanGroup INSERT must be rolled back.
    assert TimeSpanGroup.objects.count() == tsg_count_before, (
        "A TimeSpanGroup was created despite the origin write failing — "
        "the update is not atomic"
    )
    assert date_period.time_span_groups.count() == 0
    # No orphan origin must have been created either.
    assert date_period.origins.count() == 0


@pytest.mark.django_db
def test_create_date_period_with_origin(
    resource,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    api_client,
):
    """POST with a new origin creates the DatePeriod and a PeriodOrigin (201)."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")
    data = {
        "resource": resource.id,
        "name": "Testperiod with origin",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "resource_state": "undefined",
        "override": False,
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "test-origin-1",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    date_period = DatePeriod.objects.get(pk=response.data["id"])
    assert date_period.origins.count() == 1
    origin = date_period.origins.first()
    assert origin.origin_id == "test-origin-1"
    assert origin.data_source == data_source


@pytest.mark.django_db
def test_create_date_period_duplicate_origin_returns_409(
    resource,
    resource_factory,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """POST with an origin already on a DIFFERENT resource's period → 409 Conflict."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    # New period will be for `resource`; conflicting origin lives on `other_resource`.
    other_resource = resource_factory()
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    existing_period = date_period_factory(resource=other_resource)
    period_origin_factory(
        period=existing_period, data_source=data_source, origin_id="used-origin-1"
    )

    url = reverse("date_period-list")
    data = {
        "resource": resource.id,
        "name": "New period conflicting origin",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "resource_state": "undefined",
        "override": False,
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "used-origin-1",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 409, f"{response.status_code} {response.data}"
    assert "message" in response.data
    assert "date_period" in response.data
    assert str(response.data["date_period"]["id"]) == str(existing_period.id)


@pytest.mark.django_db
def test_create_date_period_duplicate_origin_no_new_period_created(
    resource,
    resource_factory,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """On 409 Conflict (cross-resource) the new DatePeriod must not be persisted."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    other_resource = resource_factory()
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    existing_period = date_period_factory(resource=other_resource)
    period_origin_factory(
        period=existing_period, data_source=data_source, origin_id="taken-origin"
    )

    period_count_before = DatePeriod.objects.count()

    url = reverse("date_period-list")
    data = {
        "resource": resource.id,
        "name": "Should not be created",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "resource_state": "undefined",
        "override": False,
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "taken-origin",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 409, f"{response.status_code} {response.data}"
    assert DatePeriod.objects.count() == period_count_before


@pytest.mark.django_db
def test_create_date_period_same_resource_origin_allowed(
    resource,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """POST with an origin already on another period of the SAME resource → 201."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    existing_period = date_period_factory(resource=resource)
    period_origin_factory(
        period=existing_period, data_source=data_source, origin_id="shared-origin"
    )

    url = reverse("date_period-list")
    data = {
        "resource": resource.id,
        "name": "New period, same resource, same origin",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "resource_state": "undefined",
        "override": False,
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "shared-origin",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"
    new_period = DatePeriod.objects.get(pk=response.data["id"])
    assert new_period.origins.filter(
        data_source=data_source, origin_id="shared-origin"
    ).exists()
    # Both periods of the same resource now hold the origin.
    assert (
        PeriodOrigin.objects.filter(
            data_source=data_source, origin_id="shared-origin"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_patch_date_period_duplicate_origin_cross_resource_returns_409(
    resource,
    resource_factory,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """PATCH that adds an origin already on a DIFFERENT resource's period → 409."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    # origin already lives on another resource's period
    other_resource = resource_factory()
    existing_period = date_period_factory(resource=other_resource)
    period_origin_factory(
        period=existing_period, data_source=data_source, origin_id="taken-origin"
    )

    # period under test has no origins yet
    date_period = date_period_factory(resource=resource, name="My period")

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})
    data = {
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "taken-origin",
            }
        ],
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 409, f"{response.status_code} {response.data}"
    assert "message" in response.data
    # The period must remain origin-free
    assert date_period.origins.count() == 0


@pytest.mark.django_db
def test_patch_date_period_reuses_existing_origin(
    resource,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """PUT/PATCH with an already-attached origin must update, not re-create it (200)."""
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    date_period = date_period_factory(resource=resource, name="Original name")
    existing_origin = period_origin_factory(
        period=date_period, data_source=data_source, origin_id="existing-origin"
    )
    origin_pk_before = existing_origin.pk

    url = reverse("date_period-detail", kwargs={"pk": date_period.pk})
    data = {
        "name": "Updated name",
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "existing-origin",
            }
        ],
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    date_period.refresh_from_db()
    assert date_period.name == "Updated name"
    # Origin must have been re-used, not re-created.
    assert PeriodOrigin.objects.filter(pk=origin_pk_before).exists()
    assert date_period.origins.filter(pk=origin_pk_before).exists()


@pytest.mark.django_db
def test_put_date_period_with_origin_from_another_period(
    resource,
    data_source_factory,
    organization_factory,
    user_origin_factory,
    user_factory,
    period_origin_factory,
    date_period_factory,
    api_client,
):
    """PUT that assigns an origin already on another period of the SAME resource
    succeeds (200) and creates a new PeriodOrigin row for the target period.
    The original row on the source period is left intact — same-resource sharing
    is explicitly allowed, so both periods end up holding the origin.
    """
    data_source = data_source_factory()
    user = user_factory()
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    organization.regular_users.add(user)
    user_origin_factory(data_source=data_source, user=user)
    api_client.force_authenticate(user=user)

    period_a = date_period_factory(resource=resource, name="Period A")
    origin = period_origin_factory(
        period=period_a, data_source=data_source, origin_id="moveable-origin"
    )
    origin_pk = origin.pk

    period_b = date_period_factory(resource=resource, name="Period B")

    url = reverse("date_period-detail", kwargs={"pk": period_b.pk})
    data = {
        "resource": resource.id,
        "name": "Period B",
        "start_date": None,
        "end_date": None,
        "resource_state": "undefined",
        "override": False,
        "origins": [
            {
                "data_source": {"id": data_source.id},
                "origin_id": "moveable-origin",
            }
        ],
        "time_span_groups": [],
    }

    response = api_client.put(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    # period_b must now have the origin.
    assert period_b.origins.filter(
        data_source=data_source, origin_id="moveable-origin"
    ).exists()

    # Both periods share the origin — same-resource sharing is explicitly allowed,
    # so exactly two PeriodOrigin rows exist for this (data_source, origin_id) pair.
    assert (
        PeriodOrigin.objects.filter(
            data_source=data_source, origin_id="moveable-origin"
        ).count()
        == 2
    )

    # The original PeriodOrigin row for period_a is still intact and unchanged.
    assert PeriodOrigin.objects.filter(pk=origin_pk).exists()
    assert PeriodOrigin.objects.get(pk=origin_pk).period == period_a
