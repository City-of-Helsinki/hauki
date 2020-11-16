import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from hours.models import (
    DatePeriod,
    Resource,
    Rule,
    TimeSpan,
    _get_all_parent_organizations,
)


#
# Resource
#
@pytest.mark.django_db
def test_create_resource_anonymous(api_client):
    url = reverse("resource-list")

    data = {"name": "Test name"}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_resource_authenticated_no_org(user, api_client):
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {"name": "Test name"}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_resource_authenticated_has_org(
    organization_factory, data_source, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_resource_authenticated_different_org(
    organization_factory, data_source, user, api_client
):
    organization1 = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )

    organization2 = organization_factory(
        origin_id=23456,
        data_source=data_source,
        name="Test organization",
    )

    organization1.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization2.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_child_resource_authenticated(
    resource, organization_factory, data_source, user, api_client
):
    organization1 = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization1
    resource.save()

    organization1.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization1.id,
        "parents": [resource.id],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )

    new_resource = Resource.objects.get(pk=response.data["id"])

    assert new_resource.parents.count() == 1


@pytest.mark.django_db
def test_create_child_resource_authenticated_parent_different_org(
    resource, organization_factory, data_source, user, api_client
):
    organization1 = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization1
    resource.save()

    organization2 = organization_factory(
        origin_id=23456,
        data_source=data_source,
        name="Test organization 2",
    )

    organization2.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization2.id,
        "parents": [resource.id],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_resource_anonymous(resource, api_client):
    original_name = resource.name

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    resource = Resource.objects.get(id=resource.id)

    assert resource.name == original_name

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_resource_authenticated_no_org_permission(
    resource, data_source, organization_factory, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    original_name = resource.name

    api_client.force_authenticate(user=user)

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    resource = Resource.objects.get(id=resource.id)

    assert resource.name == original_name

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_resource_authenticated_has_org_permission(
    resource, data_source, organization_factory, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    organization.regular_users.add(user)

    api_client.force_authenticate(user=user)

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    resource = Resource.objects.get(id=resource.id)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert resource.name == "New name"


@pytest.mark.django_db
def test_get_all_parent_organizations(
    resource_factory, data_source, organization_factory
):
    #         resource A
    #         org 1
    #             |
    #      +------+------+
    #      |             |
    # resource B     resource C
    # org 2          org 3
    #      |             |
    #      +------+------+
    #             |
    #         resource D
    #         org 4
    org1 = organization_factory(
        origin_id=1,
        data_source=data_source,
        name="Org 1",
    )
    org2 = organization_factory(
        origin_id=2,
        data_source=data_source,
        name="Org 2",
    )
    org3 = organization_factory(
        origin_id=3,
        data_source=data_source,
        name="Org 3",
    )
    org4 = organization_factory(
        origin_id=4,
        data_source=data_source,
        name="Org 4",
    )

    resource_a = resource_factory(name="Resource A", organization=org1)
    resource_b = resource_factory(name="Resource B", organization=org2)
    resource_b.parents.add(resource_a)
    resource_c = resource_factory(name="Resource C", organization=org3)
    resource_c.parents.add(resource_a)
    resource_d = resource_factory(name="Resource D", organization=org4)
    resource_d.parents.add(resource_b)
    resource_d.parents.add(resource_c)

    assert _get_all_parent_organizations(resource_d) == {org1, org2, org3}


#
# DatePeriod
#
@pytest.mark.django_db
def test_create_date_period_anonymous(api_client):
    url = reverse("date_period-list")

    data = {"name": "Date period name"}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_date_period_authenticated_no_org_in_resource(
    api_client, resource, user
):
    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    data = {
        "name": "Date period name",
        "resource": resource.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_date_period_authenticated_no_org_permission(
    api_client, organization_factory, data_source, resource, user
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    data = {
        "name": "Date period name",
        "resource": resource.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_date_period_authenticated_has_org_permission(
    api_client, organization_factory, data_source, resource, user
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    organization.regular_users.add(user)

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    data = {
        "name": "Date period name",
        "resource": resource.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_date_period_anonymous(resource, date_period_factory, api_client):
    date_period = date_period_factory(resource=resource)

    original_name = date_period.name

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    date_period = DatePeriod.objects.get(id=date_period.id)

    assert date_period.name == original_name

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_date_period_authenticated_no_org_permission(
    resource, data_source, organization_factory, date_period_factory, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)

    original_name = date_period.name

    api_client.force_authenticate(user=user)

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    date_period = DatePeriod.objects.get(id=date_period.id)

    assert date_period.name == original_name

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_date_period_authenticated_has_org_permission(
    resource, data_source, organization_factory, date_period_factory, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    date_period = DatePeriod.objects.get(id=date_period.id)

    assert date_period.name == "New name"

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )


#
# Rule
#
@pytest.mark.django_db
def test_create_rule_anonymous(api_client):
    url = reverse("rule-list")

    data = {"name": "Rule name"}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_rule_authenticated_no_org_in_resource(
    api_client, resource, date_period_factory, time_span_group_factory, user
):
    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    api_client.force_authenticate(user=user)

    url = reverse("rule-list")

    data = {
        "name": "Rule name",
        "group": time_span_group.id,
        "context": "period",
        "subject": "week",
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_rule_authenticated_no_org_permission(
    api_client,
    organization_factory,
    data_source,
    resource,
    date_period_factory,
    time_span_group_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    api_client.force_authenticate(user=user)

    url = reverse("rule-list")

    data = {
        "name": "Rule name",
        "group": time_span_group.id,
        "context": "period",
        "subject": "week",
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_rule_authenticated_has_org_permission(
    api_client,
    organization_factory,
    data_source,
    resource,
    date_period_factory,
    time_span_group_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("rule-list")

    data = {
        "name": "Rule name",
        "group": time_span_group.id,
        "context": "period",
        "subject": "week",
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_rule_anonymous(
    api_client, resource, date_period_factory, time_span_group_factory, rule_factory
):
    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    rule = rule_factory(
        name="Rule name", group=time_span_group, context="period", subject="week"
    )

    url = reverse("rule-detail", kwargs={"pk": rule.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_rule_authenticated_no_org_permission(
    api_client,
    resource,
    organization_factory,
    data_source,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    rule = rule_factory(
        name="Rule name", group=time_span_group, context="period", subject="week"
    )

    api_client.force_authenticate(user=user)

    url = reverse("rule-detail", kwargs={"pk": rule.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_rule_authenticated_has_org_permission(
    api_client,
    resource,
    organization_factory,
    data_source,
    date_period_factory,
    time_span_group_factory,
    rule_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    rule = rule_factory(
        name="Rule name", group=time_span_group, context="period", subject="week"
    )

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("rule-detail", kwargs={"pk": rule.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    rule = Rule.objects.get(pk=rule.id)
    assert rule.name == "New name"


#
# TimeSpan
#
@pytest.mark.django_db
def test_create_time_span_anonymous(api_client):
    url = reverse("time_spans-list")

    data = {"name": "Time span name"}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_time_span_authenticated_no_org_in_resource(
    api_client, resource, date_period_factory, time_span_group_factory, user
):
    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    api_client.force_authenticate(user=user)

    url = reverse("time_spans-list")

    data = {
        "name": "Time span name",
        "group": time_span_group.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_time_span_authenticated_no_org_permission(
    api_client,
    organization_factory,
    data_source,
    resource,
    date_period_factory,
    time_span_group_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    api_client.force_authenticate(user=user)

    url = reverse("time_spans-list")

    data = {
        "name": "Time span name",
        "group": time_span_group.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_create_time_span_authenticated_has_org_permission(
    api_client,
    organization_factory,
    data_source,
    resource,
    date_period_factory,
    time_span_group_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("time_spans-list")

    data = {
        "name": "Time span name",
        "group": time_span_group.id,
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_time_span_anonymous(
    api_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    time_span = time_span_factory(name="Time span name", group=time_span_group)

    url = reverse("time_spans-detail", kwargs={"pk": time_span.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_time_span_authenticated_no_org_permission(
    api_client,
    resource,
    organization_factory,
    data_source,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    time_span = time_span_factory(name="Time span name", group=time_span_group)

    api_client.force_authenticate(user=user)

    url = reverse("time_spans-detail", kwargs={"pk": time_span.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
def test_update_time_span_authenticated_has_org_permission(
    api_client,
    resource,
    organization_factory,
    data_source,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    date_period = date_period_factory(resource=resource)
    time_span_group = time_span_group_factory(period=date_period)
    time_span = time_span_factory(name="Time span name", group=time_span_group)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("time_spans-detail", kwargs={"pk": time_span.id})

    data = {
        "name": "New name",
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    time_span = TimeSpan.objects.get(pk=time_span.id)
    assert time_span.name == "New name"


@pytest.mark.django_db
def test_permission_check_action_anonymous_read(api_client, resource):
    url = reverse("resource-permission-check", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data == {
        "has_permission": True,
    }


@pytest.mark.django_db
def test_permission_check_action_anonymous_update(api_client, resource):
    url = reverse("resource-permission-check", kwargs={"pk": resource.id})

    data = {
        "name": "New name",
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data == {
        "has_permission": False,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "add_to_org, expected_value",
    (
        (False, False),
        (True, True),
    ),
)
def test_permission_check_action_authenticated_update(
    api_client,
    resource,
    organization_factory,
    data_source,
    user,
    add_to_org,
    expected_value,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    if add_to_org:
        organization.regular_users.add(user)

    api_client.force_authenticate(user=user)

    url = reverse("resource-permission-check", kwargs={"pk": resource.id})

    data = {
        "name": "New name",
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data == {
        "has_permission": expected_value,
    }
