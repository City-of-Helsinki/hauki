from unittest import mock

import pytest

from hours.utils import copy_instance


def test_copy_instance_saves_and_returns_new_instance():
    instance = mock.MagicMock(id=1)

    new_instance = copy_instance(instance)

    assert new_instance.id != instance.id
    assert new_instance.id is None
    new_instance.save.assert_called_once()


@pytest.mark.parametrize(
    "field_overrides",
    [
        {},
        {"name": "Test"},
        {"name": "Test", "description": "Test description"},
    ],
)
def test_copy_instance_returns_new_instance_with_correct_field_values_when_field_overrides_is_used(
    field_overrides,
):
    instance = mock.MagicMock()
    for field_name in field_overrides.keys():
        setattr(instance, field_name, "Old value")

    new_instance = copy_instance(instance, field_overrides)

    for field_name, field_value in field_overrides.items():
        # Old resource is not changed
        assert getattr(instance, field_name) != field_value
        # New resource has correct field value
        assert getattr(new_instance, field_name) == field_value
