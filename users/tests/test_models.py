import pytest
from django.db import IntegrityError

from users.models import UserOrigin


@pytest.mark.django_db
def test_user_origin_no_duplicate_data_source_for_a_single_user(user, data_source):
    """Duplicate UserOrigin instances are not allowed for a single user when data source
    is the same.
    """
    UserOrigin.objects.create(user=user, data_source=data_source)
    with pytest.raises(IntegrityError):
        UserOrigin.objects.create(user=user, data_source=data_source)


@pytest.mark.django_db
def test_user_origin_duplicate_data_source_allowed_for_different_users(
    user_factory, data_source
):
    """
    UserOrigin instances with the same data source are allowed for different users.
    """
    UserOrigin.objects.create(user=user_factory(), data_source=data_source)
    UserOrigin.objects.create(user=user_factory(), data_source=data_source)
