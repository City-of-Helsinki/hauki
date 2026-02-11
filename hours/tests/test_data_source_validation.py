import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from hours.models import Resource


@pytest.fixture
def user_with_data_source_origin(user, data_source, user_origin_factory):
    user_origin_factory(data_source=data_source, user=user)
    return user


@pytest.mark.django_db
def test_create_resource_with_wrong_data_source_fails(
    organization_factory,
    data_source,
    data_source_factory,
    user_with_data_source_origin,
    api_client,
):
    user = user_with_data_source_origin
    organization = organization_factory(
        origin_id=12345,
        data_source=data_source,
        name="Test organization",
    )
    another_data_source = data_source_factory()

    organization.regular_users.add(user)
    api_client.force_authenticate(user=user)

    url = reverse("resource-list")

    data = {
        "name": "Test name",
        "organization": organization.id,
        "origins": [
            {
                "data_source": {
                    "id": another_data_source.id,
                },
                "origin_id": "1",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 400, f"{response.status_code} {response.data}"
    assert "Cannot add origin_ids for a different data source" in str(response.data)


@pytest.mark.django_db
def test_patch_resource_with_wrong_data_source_allowed(
    resource,
    data_source,
    data_source_factory,
    resource_origin_factory,
    organization_factory,
    user_with_data_source_origin,
    api_client,
):
    user = user_with_data_source_origin
    resource_origin_factory(
        data_source=data_source, resource=resource, origin_id="original"
    )
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

    another_data_source = data_source_factory()
    data = {
        "origins": [
            {
                "data_source": {
                    "id": another_data_source.id,
                },
                "origin_id": "tpr",
            }
        ],
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    resource.refresh_from_db()
    assert resource.origins.count() == 1
    assert resource.origins.first().data_source.id == another_data_source.id
    assert resource.origins.first().origin_id == "tpr"


@pytest.mark.django_db
def test_put_resource_with_wrong_data_source_allowed(
    resource,
    data_source,
    data_source_factory,
    resource_origin_factory,
    organization_factory,
    user_with_data_source_origin,
    api_client,
):
    user = user_with_data_source_origin
    resource_origin_factory(
        data_source=data_source, resource=resource, origin_id="original"
    )
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

    another_data_source = data_source_factory()
    data = {
        "name": "Updated name",
        "organization": organization.id,
        "origins": [
            {
                "data_source": {
                    "id": another_data_source.id,
                },
                "origin_id": "tpr",
            }
        ],
    }

    response = api_client.put(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    resource.refresh_from_db()
    assert resource.origins.count() == 1
    assert resource.origins.first().data_source.id == another_data_source.id
    assert resource.origins.first().origin_id == "tpr"


@pytest.mark.django_db
def test_create_resource_with_correct_data_source_succeeds(
    organization_factory,
    data_source,
    user_with_data_source_origin,
    api_client,
):
    user = user_with_data_source_origin
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
        "origins": [
            {
                "data_source": {
                    "id": data_source.id,
                },
                "origin_id": "1",
            }
        ],
    }

    response = api_client.post(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201, f"{response.status_code} {response.data}"

    new_resource = Resource.objects.get(pk=response.data["id"])
    assert new_resource.origins.count() == 1
    assert new_resource.origins.first().data_source.id == data_source.id
    assert new_resource.origins.first().origin_id == "1"


@pytest.mark.django_db
def test_patch_resource_with_correct_data_source_succeeds(
    resource,
    data_source,
    resource_origin_factory,
    organization_factory,
    user_with_data_source_origin,
    api_client,
):
    user = user_with_data_source_origin
    resource_origin_factory(
        data_source=data_source, resource=resource, origin_id="original"
    )
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

    data = {
        "origins": [
            {
                "data_source": {
                    "id": data_source.id,
                },
                "origin_id": "tpr",
            }
        ],
    }

    response = api_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200, f"{response.status_code} {response.data}"

    resource.refresh_from_db()
    assert resource.origins.count() == 1
    assert resource.origins.first().data_source.id == data_source.id
    assert resource.origins.first().origin_id == "tpr"
