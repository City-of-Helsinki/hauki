import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from hours.fields import TimezoneRetainingDateTimeField


@pytest.fixture
def field():
    return TimezoneRetainingDateTimeField()


def test_enforce_timezone_aware_value_returned_as_is(field):
    aware = datetime.datetime(2021, 1, 11, 12, 0, tzinfo=datetime.UTC)
    result = field.enforce_timezone(aware)
    assert result == aware


def test_enforce_timezone_make_aware_raises_calls_fail(field):
    naive = datetime.datetime(2021, 1, 11, 12, 0)
    with patch("django.utils.timezone.make_aware", side_effect=ValueError("ambiguous")):
        with pytest.raises(ValidationError):
            field.enforce_timezone(naive)


def test_enforce_timezone_none_field_timezone_strips_timezone(field):
    aware = datetime.datetime(2021, 1, 11, 12, 0, tzinfo=datetime.UTC)
    with patch.object(field, "default_timezone", return_value=None):
        result = field.enforce_timezone(aware)
    assert timezone.is_naive(result)
    assert result == datetime.datetime(2021, 1, 11, 12, 0)
