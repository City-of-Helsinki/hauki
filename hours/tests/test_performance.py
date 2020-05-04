import pytest
from hours import models


@pytest.mark.django_db
def test_openings_create(openings):
    dailyhours = models.DailyHours()
    assert False
