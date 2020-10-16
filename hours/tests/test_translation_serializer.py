import pytest

from hours.models import Resource
from hours.serializers import ResourceSerializer


@pytest.mark.django_db
def test_to_representation(resource):
    serializer = ResourceSerializer(resource)

    assert serializer.data == {
        "address": {"en": None, "fi": resource.address_fi, "sv": None},
        "description": {"en": None, "fi": None, "sv": None},
        "extra_data": None,
        "id": resource.id,
        "last_modified_by": None,
        "name": {"en": None, "fi": resource.name_fi, "sv": None},
        "organization": None,
        "parent": None,
        "resource_type": "unit",
        "resourceorigin_set": [],
    }


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
    }

    serializer = ResourceSerializer(instance=resource, data=data)

    assert serializer.is_valid()

    serializer.save()

    saved_resource = Resource.objects.get(pk=resource.id)

    assert saved_resource.id == resource.id
    assert saved_resource.name_fi == "Name fi"
