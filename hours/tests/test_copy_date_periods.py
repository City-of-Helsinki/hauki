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
    resource.copy_all_periods_to_resource([resource])
    assert resource.date_periods.count() == 1


@pytest.mark.django_db
def test_copy_all_periods_to_resource(
    resource,
    resource_factory,
):
    create_test_periods(resource)
    resource2 = resource_factory()
    resource.copy_all_periods_to_resource([resource2])

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

    resource.copy_all_periods_to_resource([resource2], replace=replace)

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
