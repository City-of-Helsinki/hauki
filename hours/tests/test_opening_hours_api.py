import datetime

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_opening_hours_empty(admin_client):
    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_opening_hours_date_period_no_opening_hours(
    admin_client, resource, date_period_factory
):
    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 1
    assert response.data[0]["resource"]["name"]["fi"] == resource.name_fi
    assert len(response.data[0]["opening_hours"]) == 0


@pytest.mark.django_db
def test_opening_hours_two_resources_one_date_period(
    admin_client, resource_factory, date_period_factory
):
    resource = resource_factory()
    resource_factory()

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 1
    assert response.data[0]["resource"]["name"]["fi"] == resource.name_fi
    assert len(response.data[0]["opening_hours"]) == 0


@pytest.mark.django_db
def test_opening_hours_two_resources_two_date_periods(
    admin_client, resource_factory, date_period_factory
):
    resource = resource_factory()
    resource2 = resource_factory()

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    date_period_factory(
        resource=resource2,
        name="Testperiod2",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    resource_names = {i["resource"]["name"]["fi"] for i in response.data}

    assert resource_names == {resource.name_fi, resource2.name_fi}


@pytest.mark.django_db
def test_opening_hours_data_source_filter_two_resources(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource_factory,
    date_period_factory,
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    resource2 = resource_factory()
    resource_origin_factory(
        resource=resource2,
        data_source=data_source,
    )

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    date_period_factory(
        resource=resource2,
        name="Testperiod2",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
        "data_source": data_source.id,
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    resource_names = {i["resource"]["name"]["fi"] for i in response.data}

    assert resource_names == {resource.name_fi, resource2.name_fi}


@pytest.mark.django_db
def test_opening_hours_data_source_filter_two_resources_different_data_source(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource_factory,
    date_period_factory,
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    resource2 = resource_factory()
    resource_origin_factory(
        resource=resource2,
        data_source=data_source2,
    )

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    date_period_factory(
        resource=resource2,
        name="Testperiod2",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
        "data_source": data_source2.id,
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    resource_names = {i["resource"]["name"]["fi"] for i in response.data}

    assert resource_names == {resource2.name_fi}


@pytest.mark.django_db
def test_opening_hours_data_source_filter_child_has_data_source(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource_factory,
    date_period_factory,
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    resource2 = resource_factory()
    resource2.parents.set([resource])
    resource_origin_factory(
        resource=resource2,
        data_source=data_source,
    )

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    date_period_factory(
        resource=resource2,
        name="Testperiod2",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
        "data_source": data_source.id,
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    resource_names = {i["resource"]["name"]["fi"] for i in response.data}

    assert resource_names == {resource.name_fi, resource2.name_fi}


@pytest.mark.django_db
def test_opening_hours_data_source_filter_child_doesnt_have_data_source(
    admin_client,
    data_source_factory,
    resource_origin_factory,
    resource_factory,
    date_period_factory,
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(
        resource=resource,
        data_source=data_source,
    )

    resource2 = resource_factory()
    resource2.parents.set([resource])

    date_period_factory(
        resource=resource,
        name="Testperiod",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    date_period_factory(
        resource=resource2,
        name="Testperiod2",
        start_date=datetime.date(year=2020, month=1, day=1),
        end_date=datetime.date(year=2020, month=12, day=31),
    )

    url = reverse("opening_hours-list")

    data = {
        "start_date": "2020-11-01",
        "end_date": "2020-11-30",
        "data_source": data_source.id,
    }

    response = admin_client.get(
        url,
        data=data,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    resource_names = {i["resource"]["name"]["fi"] for i in response.data}

    # TODO: This is not yet working. Change when ancestor data source logic
    #       has been implemented.
    # assert resource_names == {resource.name_fi, resource2.name_fi}
    assert resource_names == {resource.name_fi}
