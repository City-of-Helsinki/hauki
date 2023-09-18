import datetime

import pytest
from django.urls import reverse
from django.utils.http import urlencode

from hours.enums import FrequencyModifier, RuleContext, RuleSubject, State, Weekday
from hours.models import TimeElement
from hours.tests.conftest import (
    DatePeriodFactory,
    RuleFactory,
    TimeSpanFactory,
    TimeSpanGroupFactory,
)

DEFAULT_YEAR = 2020
DEFAULT_START_OF_YEAR = datetime.date(year=DEFAULT_YEAR, month=1, day=1)
DEFAULT_END_OF_YEAR = datetime.date(year=DEFAULT_YEAR, month=12, day=31)


def start_of_month(month, year=DEFAULT_YEAR):
    return datetime.date(year=year, month=month, day=1)


def end_of_month(month, year=DEFAULT_YEAR):
    if month == 12:
        return datetime.date(year=year, month=month, day=31)
    return datetime.date(year=year, month=month + 1, day=1) - datetime.timedelta(days=1)


def _encode_list_of_ids(ids):
    if not (ids and isinstance(ids, list)):
        return ids
    return ",".join([str(id_) for id_ in ids])


def _post_to_api(
    client,
    resource_id,
    target_resources,
    *,
    replace: bool = None,
    date_period_ids=None,
):
    url = reverse("resource-copy-date-periods", kwargs={"pk": resource_id})

    data = {
        "target_resources": _encode_list_of_ids(target_resources),
    }
    if replace is not None:
        data["replace"] = replace
    if date_period_ids is not None:
        data["date_period_ids"] = _encode_list_of_ids(date_period_ids)

    response = client.post(url, QUERY_STRING=urlencode(data))

    return response


def assert_response_status_code(response, expected_status_code):
    """
    Assert that the response has the expected status code and print the response data if it doesn't.
    """
    assert response.status_code == expected_status_code, "{} {}".format(
        response.status_code, response.data
    )


def assert_all_date_period_opening_hours_in_resource_opening_hours(
    resource,
    date_period,
    start_date=DEFAULT_START_OF_YEAR,
    end_date=DEFAULT_END_OF_YEAR,
):
    """
    Assert that all the date period's opening hours are found in resource's opening hours.
    """
    date_period_opening_hours = date_period.get_daily_opening_hours(
        start_date=start_date, end_date=end_date
    )
    resource_opening_hours = resource.get_daily_opening_hours(
        start_date=start_date, end_date=end_date
    )

    for date in date_period_opening_hours:
        assert date in resource_opening_hours
        assert (
            date_period_opening_hours[date] == resource_opening_hours[date]
        ), f"Resource opening hours for date {date} should match date period opening hours"


def assert_date_period_opening_hours_not_in_resource_opening_hours(
    resource,
    date_period,
    start_date=DEFAULT_START_OF_YEAR,
    end_date=DEFAULT_END_OF_YEAR,
):
    """
    Assert that none of the date period's opening hours are found in resource's opening hours.
    """
    date_period_opening_hours = date_period.get_daily_opening_hours(
        start_date=start_date, end_date=end_date
    )
    resource_opening_hours = resource.get_daily_opening_hours(
        start_date=start_date, end_date=end_date
    )

    for date in date_period_opening_hours:
        if date in resource_opening_hours:
            assert (
                date_period_opening_hours[date] != resource_opening_hours[date]
            ), f"Resource opening hours for date {date} should not match date period opening hours"


def create_test_periods(resource):
    date_period = DatePeriodFactory(
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    DatePeriodFactory(
        resource=resource,
        resource_state=State.CLOSED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
        override=True,
        is_removed=True,
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    RuleFactory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.DAY,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    TimeSpanFactory(
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=Weekday.business_days(),
    )

    TimeSpanFactory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        weekdays=Weekday.weekend(),
    )


class TimeSpanGroupBuilder:
    """
    Helper class for building TimeSpanGroups.

    Usage:
    TimeSpanGroupBuilder(date_period).with_rule(...).with_time_span(...).create()
    """

    def __init__(self, date_period):
        self.date_period = date_period
        self.time_spans = []
        self.rule = None

    def with_rule(self, **kwargs):
        kwargs.setdefault("context", RuleContext.PERIOD)
        kwargs.setdefault("subject", RuleSubject.DAY)
        self.rule = kwargs
        return self

    def with_time_span(self, **kwargs):
        self.time_spans.append(kwargs)
        return self

    def create(self):
        time_span_group = TimeSpanGroupFactory(period=self.date_period)

        if self.rule is not None:
            RuleFactory(group=time_span_group, **self.rule)

        for time_span in self.time_spans:
            TimeSpanFactory(group=time_span_group, **time_span)

        return time_span_group


def check_opening_hours_same(resource1, resource2, start_date, end_date):
    resource2.refresh_from_db()
    resource1_opening_hours = resource1.get_daily_opening_hours(start_date, end_date)
    resource2_opening_hours = resource2.get_daily_opening_hours(start_date, end_date)

    assert resource2_opening_hours == resource1_opening_hours
    assert resource2.date_periods_hash == resource1.date_periods_hash
    assert resource2.date_periods_as_text == resource1.date_periods_as_text


def check_opening_hours_not_same(resource1, resource2, start_date, end_date):
    resource1_opening_hours = resource1.get_daily_opening_hours(start_date, end_date)
    resource2_opening_hours = resource2.get_daily_opening_hours(start_date, end_date)

    assert resource1_opening_hours != resource2_opening_hours
    assert resource1.date_periods_hash != resource2.date_periods_hash
    assert resource1.date_periods_as_text != resource2.date_periods_as_text


@pytest.mark.django_db
def test_copy_all_periods_to_resource_copy_to_self_prevented(resource):
    create_test_periods(resource)

    assert resource.date_periods.count() == 1
    resource.copy_periods_to_resource(resource)
    assert resource.date_periods.count() == 1


@pytest.mark.django_db
def test_copy_all_periods_to_resource(
    resource,
    resource_factory,
):
    create_test_periods(resource)
    resource2 = resource_factory()
    resource.copy_periods_to_resource(resource2)

    assert resource2.date_periods.count() == 1
    check_opening_hours_same(
        resource,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("replace", [False, True])
def test_copy_all_periods_to_resource_replace(
    resource,
    resource_factory,
    date_period_factory,
    replace,
):
    create_test_periods(resource)
    resource2 = resource_factory()

    date_period_factory(
        resource=resource2,
        resource_state=State.CLOSED,
        start_date=datetime.date(year=2020, month=10, day=13),
        end_date=datetime.date(year=2020, month=10, day=15),
        override=True,
    )

    resource.copy_periods_to_resource(resource2, replace=replace)

    if replace:
        assert resource2.date_periods.count() == 1
        check_opening_hours_same(
            resource,
            resource2,
            start_date=datetime.date(year=2020, month=10, day=12),
            end_date=datetime.date(year=2020, month=10, day=18),
        )
    else:
        assert resource2.date_periods.count() == 2
        resource2_opening_hours = resource2.get_daily_opening_hours(
            datetime.date(year=2020, month=10, day=12),
            datetime.date(year=2020, month=10, day=18),
        )
        assert resource2_opening_hours == {
            datetime.date(2020, 10, 12): [
                TimeElement(
                    start_time=datetime.time(8, 0),
                    end_time_on_next_day=False,
                    end_time=datetime.time(16, 0),
                    resource_state=State.OPEN,
                    override=False,
                    full_day=False,
                )
            ],
            datetime.date(2020, 10, 13): [
                TimeElement(
                    start_time=None,
                    end_time_on_next_day=False,
                    end_time=None,
                    resource_state=State.CLOSED,
                    override=True,
                    full_day=True,
                )
            ],
            datetime.date(2020, 10, 14): [
                TimeElement(
                    start_time=None,
                    end_time_on_next_day=False,
                    end_time=None,
                    resource_state=State.CLOSED,
                    override=True,
                    full_day=True,
                )
            ],
            datetime.date(2020, 10, 15): [
                TimeElement(
                    start_time=None,
                    end_time_on_next_day=False,
                    end_time=None,
                    resource_state=State.CLOSED,
                    override=True,
                    full_day=True,
                )
            ],
            datetime.date(2020, 10, 16): [
                TimeElement(
                    start_time=datetime.time(8, 0),
                    end_time_on_next_day=False,
                    end_time=datetime.time(16, 0),
                    resource_state=State.OPEN,
                    override=False,
                    full_day=False,
                )
            ],
            datetime.date(2020, 10, 18): [
                TimeElement(
                    start_time=datetime.time(10, 0),
                    end_time_on_next_day=False,
                    end_time=datetime.time(14, 0),
                    resource_state=State.OPEN,
                    override=False,
                    full_day=False,
                )
            ],
        }


# API


@pytest.mark.django_db
def test_copy_periods_to_resource_with_period_ids_and_replace(
    admin_client,
    resource_factory,
    date_period_factory,
):
    # Create the source resource with two date periods.
    source_resource = resource_factory()
    create_test_periods(source_resource)
    TimeSpanGroupBuilder(
        date_period_factory(
            resource=source_resource,
            resource_state=State.OPEN,
            start_date=DEFAULT_START_OF_YEAR,
            end_date=DEFAULT_END_OF_YEAR,
        )
    ).with_time_span(
        start_time=datetime.time(8),
        end_time=datetime.time(16),
        weekdays=Weekday.business_days(),
    ).with_time_span(
        start_time=datetime.time(10),
        end_time=datetime.time(14),
        weekdays=Weekday.weekend(),
    ).create()

    TimeSpanGroupBuilder(
        summer_date_period := date_period_factory(
            resource=source_resource,
            resource_state=State.OPEN,
            start_date=start_of_month(6),
            end_date=end_of_month(8),
            override=True,
        )
    ).with_time_span(
        start_time=datetime.time(10),
        end_time=datetime.time(12),
        weekdays=Weekday.business_days(),
    ).create()

    target_resource = resource_factory()
    date_period_factory(
        resource=target_resource,
        resource_state=State.CLOSED,
        start_date=DEFAULT_START_OF_YEAR,
        end_date=DEFAULT_END_OF_YEAR,
    )

    # Copy the summer date period from the source resource to the target resource.
    response = _post_to_api(
        admin_client,
        source_resource.id,
        target_resource.id,
        date_period_ids=[summer_date_period.id],
        replace=True,
    )

    assert_response_status_code(response, 200)

    target_resource.refresh_from_db()

    # Assert that the target resource has only the source resource's summer date period.
    assert target_resource.date_periods.count() == 1

    summer_period_opening_hours = summer_date_period.get_daily_opening_hours(
        DEFAULT_START_OF_YEAR, DEFAULT_END_OF_YEAR
    )
    target_resource_opening_hours = target_resource.get_daily_opening_hours(
        DEFAULT_START_OF_YEAR, DEFAULT_END_OF_YEAR
    )

    assert target_resource_opening_hours == summer_period_opening_hours
    assert summer_date_period.as_text() in target_resource.date_periods_as_text

    # Paranoia check: shouldn't copy every date period from the source resource.
    assert target_resource.date_periods_hash != source_resource.date_periods_hash


@pytest.mark.django_db
def test_copy_periods_to_resource_with_period_ids(
    admin_client,
    resource_factory,
    date_period_factory,
):
    # Create the source resource with two date periods.
    source_resource = resource_factory()
    TimeSpanGroupBuilder(
        first_date_period := date_period_factory(
            resource=source_resource,
            resource_state=State.OPEN,
            start_date=DEFAULT_START_OF_YEAR,
            end_date=DEFAULT_END_OF_YEAR,
        )
    ).with_time_span(
        start_time=datetime.time(8),
        end_time=datetime.time(16),
        weekdays=Weekday.business_days(),
    ).with_time_span(
        start_time=datetime.time(10),
        end_time=datetime.time(14),
        weekdays=Weekday.weekend(),
    ).create()

    TimeSpanGroupBuilder(
        second_date_period := date_period_factory(
            resource=source_resource,
            resource_state=State.OPEN,
            start_date=start_of_month(6),
            end_date=end_of_month(8),
            override=True,
        )
    ).with_time_span(
        start_time=datetime.time(10),
        end_time=datetime.time(12),
        weekdays=Weekday.business_days(),
    ).create()

    # Create the target resource with one date period.
    target_resource = resource_factory()
    target_resource_date_period = date_period_factory(
        resource=target_resource,
        resource_state=State.CLOSED,
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    # Copy the second date period to the target resource.
    response = _post_to_api(
        admin_client,
        source_resource.id,
        target_resource.id,
        date_period_ids=[second_date_period.id],
    )

    assert_response_status_code(response, 200)

    target_resource.refresh_from_db()

    # Assert that the target resource has its original date period and the source resource's second date period.
    assert target_resource.date_periods.count() == 2
    assert_all_date_period_opening_hours_in_resource_opening_hours(
        target_resource, second_date_period
    )
    assert second_date_period.as_text() in target_resource.date_periods_as_text
    assert target_resource_date_period.as_text() in target_resource.date_periods_as_text
    # Paranoia check: assert that the target resource does not have the source resource's first date period.
    assert first_date_period.as_text() not in target_resource.date_periods_as_text
    assert_date_period_opening_hours_not_in_resource_opening_hours(
        target_resource, first_date_period
    )


@pytest.mark.parametrize(
    "date_period_ids",
    [
        [-1],
        [-1, -2],
    ],
)
@pytest.mark.django_db
def test_copy_periods_to_resource_with_period_ids_all_missing(
    date_period_ids,
    admin_client,
    resource_factory,
):
    source_resource = resource_factory()
    target_resource = resource_factory()

    response = _post_to_api(
        admin_client,
        source_resource.id,
        target_resource.id,
        date_period_ids=date_period_ids,
    )

    assert_response_status_code(response, 404)


@pytest.mark.parametrize(
    "date_period_ids",
    [
        [-1],
        [-1, -2],
    ],
)
@pytest.mark.django_db
def test_copy_periods_to_resource_with_period_ids_some_missing(
    date_period_ids,
    admin_client,
    resource_factory,
    date_period_factory,
):
    source_resource = resource_factory()
    target_resource = resource_factory()
    date_periods = date_period_factory.create_batch(10, resource=source_resource)

    response = _post_to_api(
        admin_client,
        source_resource.id,
        target_resource.id,
        date_period_ids=date_period_ids
        + [date_period.id for date_period in date_periods],
    )

    assert_response_status_code(response, 404)


@pytest.mark.django_db
def test_resource_api_copy_date_periods_parameter_missing(admin_client, resource):
    url = reverse("resource-copy-date-periods", kwargs={"pk": resource.id})

    response = admin_client.post(url)

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_admin_user(admin_client, resource_factory):
    resource1 = resource_factory()
    resource2 = resource_factory()

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }

    response = admin_client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_admin_user_one_target_missing(
    admin_client, resource_factory
):
    resource1 = resource_factory()
    resource2 = resource_factory()

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": ",".join([str(resource2.id), "12345"]),
    }

    response = admin_client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("with_replace", [False, True])
def test_resource_api_copy_date_periods_admin_user_replace(
    admin_client, resource_factory, with_replace
):
    resource1 = resource_factory()
    resource2 = resource_factory()

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
        "replace": with_replace,
    }

    response = admin_client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("with_data_source_id", [False, True])
def test_resource_api_copy_date_periods_admin_user_copy_to_self_prevented(
    admin_client, resource, data_source, resource_origin_factory, with_data_source_id
):
    target_resources = resource.id
    if with_data_source_id:
        resource_origin = resource_origin_factory(
            resource=resource,
            data_source=data_source,
            origin_id="12345",
        )
        target_resources = "{}:{}".format(data_source.id, resource_origin.origin_id)

    create_test_periods(resource)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource.id})

    assert resource.date_periods.count() == 1

    data = {
        "target_resources": target_resources,
    }
    response = admin_client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 500, "{} {}".format(
        response.status_code, response.data
    )
    assert resource.date_periods.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("with_user", [False, True])
def test_resource_api_copy_date_periods_no_org(
    client, user, resource_factory, with_user
):
    if with_user:
        client.force_login(user)

    resource1 = resource_factory()
    resource2 = resource_factory()

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_not_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_same_org(
    client, organization_factory, resource_factory, user
):
    client.force_login(user)

    organization1 = organization_factory()
    organization1.regular_users.add(user)

    resource1 = resource_factory(organization=organization1)
    resource2 = resource_factory(organization=organization1)

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_different_from_org(
    client, organization_factory, resource_factory, user
):
    client.force_login(user)

    organization1 = organization_factory()
    organization2 = organization_factory()
    organization2.regular_users.add(user)

    resource1 = resource_factory(organization=organization1)
    resource2 = resource_factory(organization=organization2)

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_different_from_org_non_public(
    client, organization_factory, resource_factory, user
):
    client.force_login(user)

    organization1 = organization_factory()
    organization2 = organization_factory()
    organization2.regular_users.add(user)

    resource1 = resource_factory(organization=organization1, is_public=False)
    resource2 = resource_factory(organization=organization2)

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_not_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_different_to_org(
    client, organization_factory, resource_factory, user
):
    client.force_login(user)

    organization1 = organization_factory()
    organization1.regular_users.add(user)
    organization2 = organization_factory()

    resource1 = resource_factory(organization=organization1)
    resource2 = resource_factory(organization=organization2)

    create_test_periods(resource1)

    url = reverse("resource-copy-date-periods", kwargs={"pk": resource1.id})

    data = {
        "target_resources": resource2.id,
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )

    check_opening_hours_not_same(
        resource1,
        resource2,
        start_date=datetime.date(year=2020, month=10, day=12),
        end_date=datetime.date(year=2020, month=10, day=18),
    )


@pytest.mark.django_db
def test_resource_api_copy_date_periods_to_multiple(
    client, organization_factory, resource_factory, user
):
    client.force_login(user)

    organization1 = organization_factory()
    organization1.regular_users.add(user)

    resources = []
    for i in range(0, 4):
        resources.append(resource_factory(organization=organization1))

    create_test_periods(resources[0])

    url = reverse("resource-copy-date-periods", kwargs={"pk": resources[0].id})

    data = {
        "target_resources": ",".join([str(r.id) for r in resources[1:]]),
    }
    response = client.post(url, QUERY_STRING=urlencode(data))

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    for i in range(1, 4):
        check_opening_hours_same(
            resources[0],
            resources[i],
            start_date=datetime.date(year=2020, month=10, day=12),
            end_date=datetime.date(year=2020, month=10, day=18),
        )
