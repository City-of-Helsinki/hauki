import pytest
from django.db import IntegrityError

from users.models import UserOrigin


@pytest.mark.django_db
def test_user_origin_shouldnt_allow_duplicate_empty_origin_id(user, data_source):
    """Duplicate UserOrigin instances shouldn't get created when data source is
    the same but origin_id is empty.
    """
    UserOrigin.objects.create(user=user, data_source=data_source)
    with pytest.raises(IntegrityError):
        UserOrigin.objects.create(user=user, data_source=data_source)
