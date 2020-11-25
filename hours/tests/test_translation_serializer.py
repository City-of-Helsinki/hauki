import pytest

from hours.models import Resource
from hours.serializers import ResourceSerializer


@pytest.mark.django_db
def test_to_representation(resource):
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

    assert saved_resource.id == resource.id
    assert saved_resource.name_fi == "Name fi"
    assert not saved_resource.is_public
