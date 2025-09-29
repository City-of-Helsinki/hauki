import datetime
import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from hours.enums import State
from hours.serializers import TimeSpanGroupSerializer


@pytest.mark.django_db
def test_create_time_span_direct(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    url = reverse("time_span-list")

    data = {
        "group": time_span_group.id,
        "name": {
            "fi": "Test name fi",
            "sv": "Test name sv",
            "en": "Test name en",
        },
        "description": {
            "fi": "Test description fi",
            "sv": "Test description sv",
            "en": "Test description en",
        },
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "full_day": False,
        "weekdays": [1, 2, 3],
        "resource_state": "open",
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    names = {i for i in response.data.get("name").items()}
    assert names == {
        ("fi", "Test name fi"),
        ("sv", "Test name sv"),
        ("en", "Test name en"),
    }


@pytest.mark.django_db
def test_create_time_span_nested_using_api_endpoint(
    admin_client,
    resource,
    date_period_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    data = {
        "id": date_period.id,
        "resource": resource.id,
        "time_span_groups": [
            {
                "period": date_period.id,
                "time_spans": [
                    {
                        "name": {
                            "fi": "Test name fi",
                            "sv": "Test name sv",
                            "en": "Test name en",
                        },
                        "description": {
                            "fi": "Test description fi",
                            "sv": "Test description sv",
                            "en": "Test description en",
                        },
                        "start_time": "08:00:00",
                        "end_time": "16:00:00",
                        "full_day": False,
                        "weekdays": [1, 2, 3],
                        "resource_state": "open",
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

    names = {
        i
        for i in response.data.get("time_span_groups")[0]
        .get("time_spans")[0]
        .get("name")
        .items()
    }
    assert names == {
        ("fi", "Test name fi"),
        ("sv", "Test name sv"),
        ("en", "Test name en"),
    }


@pytest.mark.django_db
def test_create_time_span_nested_using_serializer(
    admin_client,
    resource,
    date_period_factory,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    data = {
        "period": date_period.id,
        "time_spans": [
            {
                "name": {
                    "fi": "Test name fi",
                    "sv": "Test name sv",
                    "en": "Test name en",
                },
                "description": {
                    "fi": "Test description fi",
                    "sv": "Test description sv",
                    "en": "Test description en",
                },
                "start_time": "08:00:00",
                "end_time": "16:00:00",
                "full_day": False,
                "weekdays": [1, 2, 3],
                "resource_state": "open",
            },
        ],
    }

    serializer = TimeSpanGroupSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    time_span = serializer.data.get("time_spans")[0]
    names = {i for i in time_span.get("name").items()}
    assert names == {
        ("fi", "Test name fi"),
        ("sv", "Test name sv"),
        ("en", "Test name en"),
    }

    descriptions = {i for i in time_span.get("description").items()}
    assert descriptions == {
        ("fi", "Test description fi"),
        ("sv", "Test description sv"),
        ("en", "Test description en"),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("same_day_time", [True, False])
def test_create_time_span_same_day_end_time(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    same_day_time,
):
    date_period = date_period_factory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    url = reverse("time_span-list")

    data = {
        "group": time_span_group.id,
        "name": {
            "fi": "Test name fi",
            "sv": "Test name sv",
            "en": "Test name en",
        },
        "description": {
            "fi": "Test description fi",
            "sv": "Test description sv",
            "en": "Test description en",
        },
        "start_time": "08:00:00",
        "end_time": "16:00:00" if same_day_time else "04:00:00",
        "full_day": False,
        "weekdays": [1, 2, 3],
        "resource_state": "open",
    }

    response = admin_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    assert response.data["end_time_on_next_day"] == (not same_day_time)
