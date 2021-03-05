import json
import urllib.parse

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from hours.models import DatePeriod, Resource, Rule, TimeSpan
from hours.permissions import filter_queryset_by_permission


#
# Resource
#
@pytest.mark.django_db
def test_get_public_resource_anonymous(resource, api_client):
    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_non_public_resource_anonymous(resource, api_client):
    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_child_of_non_public_resource_anonymous(
    resource, resource_factory, api_client
):
    child_resource = resource_factory(name="Test name")
    child_resource.parents.add(resource)
    url = reverse("resource-detail", kwargs={"pk": child_resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_non_public_resource_authenticated_no_org(resource, user, api_client):
    api_client.force_authenticate(user=user)

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_non_public_resource_authenticated_has_org(
    organization_factory, data_source, resource, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)
    resource.organization = organization
    resource.save()

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_non_public_resource_authenticated_parent_org(
    organization_factory, data_source, resource, user, api_client
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
    organization2.parent = organization1
    organization2.save()
    api_client.force_authenticate(user=user)
    resource.organization = organization2
    resource.save()

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("resource__is_public", [False])
def test_get_non_public_resource_authenticated_different_org(
    organization_factory, data_source, resource, user, api_client
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
    resource.organization = organization2
    resource.save()

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
    )

    assert response.status_code == 404, "{} {}".format(
        response.status_code, response.data
    )


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
def test_create_resource_authenticated_parent_org(
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

    organization2.parent = organization1
    organization2.save()
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
def test_create_child_resource_authenticated_parent_has_different_org(
    resource, resource_factory, organization_factory, data_source, user, api_client
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
    resource2 = resource_factory(name="Test resource", organization=organization2)
    organization2.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization2.id,
        "parents": [resource.id, resource2.id],
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
def test_update_resource_authenticated_has_parent_org_permission(
    resource, data_source, organization_factory, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()

    organization2 = organization_factory(
        origin_id=23456,
        data_source=data_source,
        name="Test organization",
    )
    organization.parent = organization2
    organization.save()
    organization2.regular_users.add(user)
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
def test_update_child_resource_authenticated(
    resource, resource_factory, organization_factory, data_source, user, api_client
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    sub_resource = resource_factory(name="Test resource", organization=organization)
    sub_resource.parents.add(resource)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-detail", kwargs={"pk": sub_resource.id})

    data = {
        "parents": [],
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    sub_resource = Resource.objects.get(pk=sub_resource.id)

    assert sub_resource.parents.count() == 0


@pytest.mark.django_db
def test_update_child_resource_authenticated_parent_has_different_org(
    resource, resource_factory, organization_factory, data_source, user, api_client
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
    resource2 = resource_factory(name="Test resource", organization=organization2)
    sub_resource = resource_factory(name="Test resource", organization=organization2)
    sub_resource.parents.add(resource)
    sub_resource.parents.add(resource2)

    organization2.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-detail", kwargs={"pk": sub_resource.id})

    data = {
        "parents": [],
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
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, True),
        (False, True, True, True),
        (False, True, False, True),
        (True, True, None, True),
        (True, True, True, True),
        (True, True, False, True),
    ],
)
def test_get_non_public_resource_hsa_authenticated(
    resource,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.is_public = False
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    assert response.status_code == 200 if should_succeed else 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, True),
        (False, True, True, True),
        (False, True, False, True),
        (True, True, None, True),
        (True, True, True, True),
        (True, True, False, True),
    ],
)
def test_get_child_of_non_public_resource_hsa_authenticated(
    resource,
    resource_origin_factory,
    resource_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.is_public = False
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)

    child_resource = resource_factory(name="Child resource")
    child_resource.parents.add(resource)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": child_resource.id})

    response = api_client.get(
        url,
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    assert response.status_code == 200 if should_succeed else 404, "{} {}".format(
        response.status_code, response.data
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, True),
        (False, True, True, True),
        (False, True, False, True),
        (True, True, None, True),
        (True, True, True, True),
        (True, True, False, True),
    ],
)
def test_create_resource_hsa_authenticated_child_resource_permissions(
    resource,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-list")

    data = {"name": "New name", "parents": [resource.id]}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    if should_succeed:
        assert response.status_code == 201, "{} {}".format(
            response.status_code, response.data
        )
        child_resource = resource.children.all()[0]
        assert child_resource.name == "New name"
    else:
        assert response.status_code == 400, "{} {}".format(
            response.status_code, response.data
        )
        assert not resource.children.all()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, False),
        (False, True, True, False),
        (False, True, False, False),
        (True, True, None, False),
        (True, True, True, True),
        (True, True, False, False),
    ],
)
def test_create_resource_hsa_authenticated_child_resource_with_different_parents(
    resource,
    resource_factory,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)
    second_parent = resource_factory(name="Second parent resource")
    second_parent.organization = organization
    second_parent.save()
    resource_origin_factory(resource=second_parent, data_source=data_source)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-list")

    data = {"name": "New name", "parents": [resource.id, second_parent.id]}

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    if should_succeed:
        assert response.status_code == 201, "{} {}".format(
            response.status_code, response.data
        )
        child_resource = resource.children.all()[0]
        assert child_resource.name == "New name"
    else:
        assert response.status_code == 400, "{} {}".format(
            response.status_code, response.data
        )
        assert not resource.children.all()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, True),
        (False, True, True, True),
        (False, True, False, True),
        (True, True, None, True),
        (True, True, True, True),
        (True, True, False, True),
    ],
)
def test_update_resource_hsa_authenticated_resource_permissions(
    resource,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)
    existing_name = resource.name

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": resource.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    resource = Resource.objects.get(id=resource.id)

    if should_succeed:
        assert response.status_code == 200, "{} {}".format(
            response.status_code, response.data
        )

        assert resource.name == "New name"
    else:
        assert response.status_code == 403, "{} {}".format(
            response.status_code, response.data
        )

        assert resource.name == existing_name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, True),
        (False, True, True, True),
        (False, True, False, True),
        (True, True, None, True),
        (True, True, True, True),
        (True, True, False, True),
    ],
)
def test_update_resource_hsa_authenticated_child_resource_permissions(
    resource,
    resource_factory,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)

    child_resource = resource_factory(name="Child resource")
    child_resource.parents.add(resource)
    existing_name = child_resource.name

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": child_resource.id})

    data = {"name": "New child resource name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    child_resource = Resource.objects.get(id=child_resource.id)

    if should_succeed:
        assert response.status_code == 200, "{} {}".format(
            response.status_code, response.data
        )

        assert child_resource.name == "New child resource name"
    else:
        assert response.status_code == 403, "{} {}".format(
            response.status_code, response.data
        )

        assert child_resource.name == existing_name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, False),
        (False, True, True, False),
        (False, True, False, False),
        (True, True, None, False),
        (True, True, True, True),
        (True, True, False, False),
    ],
)
def test_update_resource_hsa_authenticated_child_resource_with_different_parents(  # noqa
    resource,
    resource_factory,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)
    second_parent = resource_factory(name="Second parent resource")
    second_parent.organization = organization
    second_parent.save()
    resource_origin_factory(resource=second_parent, data_source=data_source)

    child_resource = resource_factory(name="Child resource")
    child_resource.parents.add(resource)
    child_resource.parents.add(second_parent)
    existing_name = child_resource.name

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": child_resource.id})

    data = {"name": "New child resource name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    child_resource = Resource.objects.get(id=child_resource.id)

    if should_succeed:
        assert response.status_code == 200, "{} {}".format(
            response.status_code, response.data
        )

        assert child_resource.name == "New child resource name"
    else:
        assert response.status_code == 403, "{} {}".format(
            response.status_code, response.data
        )

        assert child_resource.name == existing_name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, False),
        (False, True, True, False),
        (False, True, False, False),
        (True, True, None, False),
        (True, True, True, True),
        (True, True, False, False),
    ],
)
def test_update_resource_hsa_authenticated_add_another_parent_to_child(
    resource,
    resource_factory,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)
    second_parent = resource_factory(name="Second parent resource")
    second_parent.organization = organization
    second_parent.save()
    resource_origin_factory(resource=second_parent, data_source=data_source)

    child_resource = resource_factory(name="Child resource")
    child_resource.parents.add(resource)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": child_resource.id})

    data = {"parents": [resource.id, second_parent.id]}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    child_resource = Resource.objects.get(id=child_resource.id)

    if should_succeed:
        assert response.status_code == 200, "{} {}".format(
            response.status_code, response.data
        )

        assert set(child_resource.parents.all()) == {resource, second_parent}
    elif set_hsa_resource:
        assert response.status_code == 400, "{} {}".format(
            response.status_code, response.data
        )

        assert set(child_resource.parents.all()) == {resource}
    else:
        assert response.status_code == 403, "{} {}".format(
            response.status_code, response.data
        )

        assert set(child_resource.parents.all()) == {resource}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_hsa_organization,set_hsa_resource,has_organization_rights,should_succeed",
    [
        (False, False, None, False),
        (False, False, True, False),
        (False, False, False, False),
        (True, False, None, False),
        (True, False, True, True),
        (True, False, False, False),
        (False, True, None, False),
        (False, True, True, False),
        (False, True, False, False),
        (True, True, None, False),
        (True, True, True, True),
        (True, True, False, False),
    ],
)
def test_update_resource_hsa_authenticated_same_org_other_resource_permissions(
    resource,
    resource_factory,
    resource_origin_factory,
    data_source,
    organization_factory,
    user,
    user_origin_factory,
    api_client,
    hsa_params_factory,
    set_hsa_organization,
    set_hsa_resource,
    has_organization_rights,
    should_succeed,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource.organization = organization
    resource.save()
    resource_origin_factory(resource=resource, data_source=data_source)

    other_resource = resource_factory(name="Other resource", organization=organization)
    existing_name = other_resource.name
    resource_origin_factory(resource=other_resource, data_source=data_source)

    user_origin_factory(user=user, data_source=data_source)
    hsa_params = {
        "user": user,
        "data_source": data_source,
    }
    if set_hsa_organization:
        hsa_params["organization"] = organization
    if set_hsa_resource:
        hsa_params["resource"] = resource
    if has_organization_rights is not None:
        hsa_params["has_organization_rights"] = has_organization_rights
    params = hsa_params_factory(**hsa_params)
    authz_string = "haukisigned " + urllib.parse.urlencode(params)

    url = reverse("resource-detail", kwargs={"pk": other_resource.id})

    data = {"name": "New other resource name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
        HTTP_AUTHORIZATION=authz_string,
    )

    other_resource = Resource.objects.get(id=other_resource.id)

    if should_succeed:
        assert response.status_code == 200, "{} {}".format(
            response.status_code, response.data
        )

        assert other_resource.name == "New other resource name"
    else:
        assert response.status_code == 403, "{} {}".format(
            response.status_code, response.data
        )

        assert other_resource.name == existing_name


@pytest.mark.django_db
def test_filter_queryset_by_read_permission(
    resource_factory, data_source, organization_factory, user
):
    #         resource A
    #         org 1
    #         public
    #             |
    #      +------+------+
    #      |             |
    # resource B     resource C
    # org 2          org 3
    # public         non-public
    #      |             |
    #      +------+------+
    #             |
    #         resource D
    #         org 4
    #         non-public

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
    resource_c = resource_factory(name="Resource C", organization=org3, is_public=False)
    resource_c.parents.add(resource_a)
    resource_d = resource_factory(name="Resource D", organization=org4, is_public=False)
    resource_d.parents.add(resource_b)
    resource_d.parents.add(resource_c)

    queryset = Resource.objects.all()

    # non-organization user only sees public resources
    filtered = filter_queryset_by_permission(user, queryset)
    assert len(filtered) == 2
    assert set(filtered) == {
        resource_a,
        resource_b,
    }

    # org4 user doesn't see org4 resource_d, because he doesn't belong
    # to parent org3 or org2
    org4.regular_users.add(user)
    filtered = filter_queryset_by_permission(user, queryset)
    assert len(filtered) == 2
    assert set(filtered) == {
        resource_a,
        resource_b,
    }
    org4.regular_users.remove(user)

    # org4 resource_d is visible if user belongs to org2 or org3
    org3.regular_users.add(user)
    filtered = filter_queryset_by_permission(user, queryset)
    assert len(filtered) == 3
    assert set(filtered) == {
        resource_a,
        resource_b,
        resource_d,
    }
    org3.regular_users.remove(user)
    org2.regular_users.add(user)
    filtered = filter_queryset_by_permission(user, queryset)
    assert len(filtered) == 3
    assert set(filtered) == {
        resource_a,
        resource_b,
        resource_d,
    }
    org2.regular_users.remove(user)

    # all resources are only visible if user belongs to org1
    org1.regular_users.add(user)
    filtered = filter_queryset_by_permission(user, queryset)
    assert len(filtered) == 4
    assert set(filtered) == {
        resource_a,
        resource_b,
        resource_c,
        resource_d,
    }


#
# DatePeriod
#
@pytest.mark.django_db
def test_list_date_periods_public(
    api_client,
    organization_factory,
    data_source,
    resource_factory,
    date_period_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource = resource_factory(organization=organization)
    date_period = date_period_factory(resource=resource)

    organization2 = organization_factory(
        origin_id=22222,
        data_source=data_source,
        name="Test organization 2",
    )
    resource2 = resource_factory(organization=organization2)
    date_period2 = date_period_factory(resource=resource2)

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    response = api_client.get(
        url, content_type="application/json", data={"start_date_gte": "1970-01-01"}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 2

    date_period_ids = {i["id"] for i in response.data}

    assert date_period_ids == {date_period.id, date_period2.id}


@pytest.mark.django_db
def test_list_date_periods_one_non_public_unauthenticated(
    api_client, organization_factory, data_source, resource_factory, date_period_factory
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource = resource_factory(organization=organization, is_public=False)
    date_period_factory(resource=resource)

    organization2 = organization_factory(
        origin_id=22222,
        data_source=data_source,
        name="Test organization 2",
    )
    resource2 = resource_factory(organization=organization2)
    date_period2 = date_period_factory(resource=resource2)

    url = reverse("date_period-list")

    response = api_client.get(
        url, content_type="application/json", data={"start_date_gte": "1970-01-01"}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 1

    date_period_ids = {i["id"] for i in response.data}

    assert date_period_ids == {date_period2.id}


@pytest.mark.django_db
def test_list_date_periods_one_non_public_authenticated_user_not_in_org(
    api_client,
    organization_factory,
    data_source,
    resource_factory,
    date_period_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource = resource_factory(organization=organization, is_public=False)
    date_period_factory(resource=resource)

    organization2 = organization_factory(
        origin_id=22222,
        data_source=data_source,
        name="Test organization 2",
    )
    resource2 = resource_factory(organization=organization2)
    date_period2 = date_period_factory(resource=resource2)

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    response = api_client.get(
        url, content_type="application/json", data={"start_date_gte": "1970-01-01"}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 1

    date_period_ids = {i["id"] for i in response.data}

    assert date_period_ids == {date_period2.id}


@pytest.mark.django_db
def test_list_date_periods_one_non_public_authenticated_user_in_org(
    api_client,
    organization_factory,
    data_source,
    resource_factory,
    date_period_factory,
    user,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    resource = resource_factory(organization=organization, is_public=False)
    date_period = date_period_factory(resource=resource)

    organization2 = organization_factory(
        origin_id=22222,
        data_source=data_source,
        name="Test organization 2",
    )
    resource2 = resource_factory(organization=organization2)
    date_period2 = date_period_factory(resource=resource2)

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    response = api_client.get(
        url, content_type="application/json", data={"start_date_gte": "1970-01-01"}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert len(response.data) == 2

    date_period_ids = {i["id"] for i in response.data}

    assert date_period_ids == {date_period.id, date_period2.id}


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
def test_create_date_period_authenticated_has_parent_resource_org_permission(
    api_client, organization_factory, resource_factory, data_source, resource, user
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    organization.regular_users.add(user)

    resource.organization = organization
    resource.save()
    child_resource = resource_factory(name="Test name")
    child_resource.parents.add(resource)

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    data = {
        "name": "Date period name",
        "resource": child_resource.id,
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
def test_create_date_period_authenticated_parent_resource_has_different_org(
    api_client, organization_factory, resource_factory, data_source, resource, user
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
    resource2 = resource_factory(name="Test resource", organization=organization2)
    organization2.regular_users.add(user)

    child_resource = resource_factory(name="Test name")
    child_resource.parents.add(resource)
    child_resource.parents.add(resource2)

    api_client.force_authenticate(user=user)

    url = reverse("date_period-list")

    data = {
        "name": "Date period name",
        "resource": child_resource.id,
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


@pytest.mark.django_db
def test_update_date_period_authenticated_has_parent_resource_org_permission(
    resource,
    data_source,
    resource_factory,
    organization_factory,
    date_period_factory,
    user,
    api_client,
):
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    organization.regular_users.add(user)

    resource.organization = organization
    resource.save()
    child_resource = resource_factory(name="Test name")
    child_resource.parents.add(resource)

    api_client.force_authenticate(user=user)

    date_period = date_period_factory(resource=child_resource)

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


@pytest.mark.django_db
def test_update_date_period_authenticated_parent_resource_has_different_org(
    resource,
    data_source,
    organization_factory,
    resource_factory,
    date_period_factory,
    user,
    api_client,
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
    resource2 = resource_factory(name="Test resource", organization=organization2)
    organization2.regular_users.add(user)

    child_resource = resource_factory(name="Test name")
    child_resource.parents.add(resource)
    child_resource.parents.add(resource2)

    api_client.force_authenticate(user=user)

    date_period = date_period_factory(resource=child_resource)
    original_name = date_period.name

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    data = {"name": "New name"}

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    date_period = DatePeriod.objects.get(id=date_period.id)

    assert response.status_code == 403, "{} {}".format(
        response.status_code, response.data
    )

    assert date_period.name == original_name


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
    url = reverse("time_span-list")

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

    url = reverse("time_span-list")

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

    url = reverse("time_span-list")

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

    url = reverse("time_span-list")

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

    url = reverse("time_span-detail", kwargs={"pk": time_span.id})

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

    url = reverse("time_span-detail", kwargs={"pk": time_span.id})

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

    url = reverse("time_span-detail", kwargs={"pk": time_span.id})

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
