import pytest

from hours.models import Resource
from hours.serializers import ResourceSerializer


@pytest.mark.django_db
def test_to_representation(resource, settings):
    serializer = ResourceSerializer(resource)
    expected_data = {
        "address": {"en": None, "fi": resource.address_fi, "sv": None},
        "description": {"en": None, "fi": None, "sv": None},
        "extra_data": None,
        "id": resource.id,
        "last_modified_by": None,
        "name": {"en": None, "fi": resource.name_fi, "sv": None},
        "organization": None,
        "parents": [],
        "children": [],
        "resource_type": "unit",
        "origins": [],
        "is_public": True,
        "timezone": "Europe/Helsinki",
    }

    assert serializer.data == expected_data


@pytest.mark.django_db
def test_to_internal_value(resource):
    data = {
        "address": {"en": None, "fi": "Test address_fi", "sv": "Test address sv"},
        "description": {"en": None, "fi": None, "sv": None},
        "extra_data": None,
        "id": resource.id,
        "last_modified_by": None,
        "name": {"en": "Name en", "fi": "Name fi", "sv": None},
        "organization": None,
        "resource_type": "unit",
        "is_public": False,
    }

    serializer = ResourceSerializer(instance=resource, data=data)

    assert serializer.is_valid()

    serializer.save()

    saved_resource = Resource.objects.get(pk=resource.id)

    assert not saved_resource.is_public
    assert saved_resource.id == resource.id
    assert saved_resource.name_fi == "Name fi"
    assert saved_resource.name_en == "Name en"
    assert saved_resource.name_sv is None


@pytest.mark.django_db
def test_to_internal_value_partial_update(resource_factory):
    resource = resource_factory(
        name_fi="Test name fi",
        name_sv="Test name sv",
        name_en="Test name en",
    )

    data = {
        "id": resource.id,
        "name": {"fi": "New name fi", "sv": None},
    }

    serializer = ResourceSerializer(instance=resource, data=data)

    assert serializer.is_valid()

    serializer.save()

    saved_resource = Resource.objects.get(pk=resource.id)

    assert saved_resource.id == resource.id
    assert saved_resource.name_fi == "New name fi"
    assert saved_resource.name_en == "Test name en"
    assert saved_resource.name_sv is None
