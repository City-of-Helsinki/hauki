from datetime import time

import pytest

from hours.enums import State, Weekday
from hours.importer.kirjastot import KirjastotImporter
from hours.tests.conftest import ResourceFactory


@pytest.mark.django_db
def test_get_kirkanta_periods():
    importer = KirjastotImporter({})
    resource = ResourceFactory()

    def get_data():
        return {
            "origins": [{"origin_id": 13, "data_source_id": importer.data_source.id}],
            "resource": resource,
            "time_span_groups": [
                {
                    "rules": [],
                    "time_spans": [
                        {
                            "group": None,
                            "start_time": time(hour=15, minute=0),
                            "end_time": time(hour=20, minute=0),
                            "weekdays": [Weekday.SATURDAY],
                            "resource_state": State.OPEN,
                            "full_day": False,
                        },
                        {
                            "group": None,
                            "start_time": time(hour=7, minute=0),
                            "end_time": time(hour=15, minute=0),
                            "weekdays": [Weekday.SATURDAY],
                            "resource_state": State.SELF_SERVICE,
                            "full_day": False,
                        },
                        {
                            "group": None,
                            "start_time": time(hour=20, minute=0),
                            "end_time": time(hour=21, minute=0),
                            "weekdays": [Weekday.SATURDAY],
                            "resource_state": State.SELF_SERVICE,
                            "full_day": False,
                        },
                    ],
                }
            ],
        }

    importer.save_dateperiod(get_data())
    importer.save_dateperiod(get_data())
    date_period = importer.save_dateperiod(get_data())

    assert date_period.history.all().count() == 2
    time_span_groups = date_period.time_span_groups.all()
    assert len(time_span_groups) == 1
    time_span_group = time_span_groups[0]
    time_spans = time_span_group.time_spans.all()
    assert len(time_spans) == 3
    for time_span in time_spans:
        # This would be 3 if history is incorrectly saved on every call
        assert time_span.history.all().count() == 1
