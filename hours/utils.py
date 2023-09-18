from copy import deepcopy
from typing import TypeVar

from django.db import models

T = TypeVar("T", bound=models.Model)


def get_resource_pk_filter(pk):
    if ":" not in pk:
        return {"pk": pk}

    # Find the object using resource origin
    data_source_id, origin_id = pk.split(":", 1)
    return {
        "origins__data_source_id": data_source_id,
        "origins__origin_id": origin_id,
    }


def copy_instance(instance: T, field_overrides: dict = None) -> T:
    new_instance = deepcopy(instance)
    new_instance.id = None
    for field_name, field_value in (field_overrides or {}).items():
        setattr(new_instance, field_name, field_value)
    new_instance.save()

    return new_instance
