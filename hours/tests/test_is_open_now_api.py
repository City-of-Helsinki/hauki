import datetime

import pytest
from django.urls import reverse
from freezegun import freeze_time

from hours.enums import State, Weekday


@pytest.mark.django_db
def test_is_open_no_spans(admin_client, resource):
    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is False
    assert response.data["resource"]["id"] == resource.id
    assert len(response.data["matching_opening_hours"]) == 0


@pytest.mark.django_db
def test_is_open_one_match(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_is_open_full_day_match(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=None,
        end_time=None,
        resource_state=State.OPEN,
        full_day=True,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_is_open_unknown_start_match(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=None,
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_is_open_unknown_end_match(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=None,
        resource_state=State.OPEN,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_is_open_one_non_open(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.CLOSED,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is False
    assert len(response.data["matching_opening_hours"]) == 0


@pytest.mark.django_db
def test_is_open_one_matching_and_non_open(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
    )

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.CLOSED,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_is_open_one_match_with_other_timezone(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        resource_state=State.OPEN,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 12:00:00+02:00"):
        response = admin_client.get(url, data={"timezone": "UTC"})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1
    assert len(response.data["matching_opening_hours_in_other_tz"]) == 1

    te = response.data["matching_opening_hours_in_other_tz"][0]
    assert te["start_time"] == "06:00:00"
    assert te["end_time"] == "14:00:00"

    assert response.data["resource_time_now"] == "2021-01-11T12:00:00+02:00"
    assert response.data["resource_timezone"] == "Europe/Helsinki"
    assert response.data["other_timezone_time_now"] == "2021-01-11T10:00:00Z"
    assert response.data["other_timezone"] == "UTC"


@pytest.mark.django_db
def test_is_open_one_match_timezone_day_difference(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=6, minute=0),
        resource_state=State.OPEN,
        weekdays=[Weekday.TUESDAY],
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 23:00:00+00:00"):
        response = admin_client.get(url, data={"timezone": "UTC"})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1
    assert len(response.data["matching_opening_hours_in_other_tz"]) == 1

    te = response.data["matching_opening_hours"][0]
    assert te["start_time"] == "00:00:00"
    assert te["end_time"] == "06:00:00"

    other_te = response.data["matching_opening_hours_in_other_tz"][0]
    assert other_te["start_time"] == "22:00:00"
    assert other_te["end_time"] == "04:00:00"

    assert response.data["resource_time_now"] == "2021-01-12T01:00:00+02:00"
    assert response.data["resource_timezone"] == "Europe/Helsinki"
    assert response.data["other_timezone_time_now"] == "2021-01-11T23:00:00Z"
    assert response.data["other_timezone"] == "UTC"


@pytest.mark.django_db
def test_is_open_one_match_from_previous_day(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2021, month=1, day=31),
    )

    time_span_group = time_span_group_factory(period=date_period)

    time_span_factory(
        group=time_span_group,
        start_time=datetime.time(hour=21, minute=0),
        end_time=datetime.time(hour=3, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2021-01-11 02:00:00+02:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1
