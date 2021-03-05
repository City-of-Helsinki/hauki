import datetime
import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from hours.enums import RuleContext, RuleSubject, State, Weekday
from hours.models import DatePeriod


@pytest.mark.django_db
def test_list_date_periods_empty(admin_client):
    url = reverse("date_period-list")

    response = admin_client.get(url, data={"start_date_lte": "2030-01-01"})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 1
    assert response.data[0]["id"] == date_period.id


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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )

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

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )
