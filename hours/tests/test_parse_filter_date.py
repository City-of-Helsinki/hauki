import datetime

import pytest
from freezegun import freeze_time

from hours.filters import parse_maybe_relative_date_string


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input_string, end_date, frozen_date, expected_date",
    (
        # Special strings
        ("today", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        # Dates
        ("1980-11-13", False, "2020-11-13", datetime.date(year=1980, month=11, day=13)),
        ("2020-11-13", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("2020-1-1", False, "2020-11-13", datetime.date(year=2020, month=1, day=1)),
        ("2020-12-31", False, "2020-11-13", datetime.date(year=2020, month=12, day=31)),
        ("2000-6-6", False, "2020-11-13", datetime.date(year=2000, month=6, day=6)),
        ("2050-6-6", False, "2020-11-13", datetime.date(year=2050, month=6, day=6)),
        # Spaces
        ("- 0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("+ 0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("-  0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("+  0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        # Zero start
        ("-0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("+0d", False, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("-0w", False, "2020-11-13", datetime.date(year=2020, month=11, day=9)),
        ("+0w", False, "2020-11-13", datetime.date(year=2020, month=11, day=9)),
        ("-0m", False, "2020-11-13", datetime.date(year=2020, month=11, day=1)),
        ("+0m", False, "2020-11-13", datetime.date(year=2020, month=11, day=1)),
        ("-0y", False, "2020-11-13", datetime.date(year=2020, month=1, day=1)),
        ("+0y", False, "2020-11-13", datetime.date(year=2020, month=1, day=1)),
        # Zero end
        ("-0d", True, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("+0d", True, "2020-11-13", datetime.date(year=2020, month=11, day=13)),
        ("-0w", True, "2020-11-13", datetime.date(year=2020, month=11, day=15)),
        ("+0w", True, "2020-11-13", datetime.date(year=2020, month=11, day=15)),
        ("-0m", True, "2020-11-13", datetime.date(year=2020, month=11, day=30)),
        ("+0m", True, "2020-11-13", datetime.date(year=2020, month=11, day=30)),
        ("-0y", True, "2020-11-13", datetime.date(year=2020, month=12, day=31)),
        ("+0y", True, "2020-11-13", datetime.date(year=2020, month=12, day=31)),
        # One difference start
        ("+1d", False, "2020-11-13", datetime.date(year=2020, month=11, day=14)),
        ("-1d", False, "2020-11-13", datetime.date(year=2020, month=11, day=12)),
        ("+1w", False, "2020-11-13", datetime.date(year=2020, month=11, day=16)),
        ("-1w", False, "2020-11-13", datetime.date(year=2020, month=11, day=2)),
        ("+1m", False, "2020-11-13", datetime.date(year=2020, month=12, day=1)),
        ("-1m", False, "2020-11-13", datetime.date(year=2020, month=10, day=1)),
        ("+1y", False, "2020-11-13", datetime.date(year=2021, month=1, day=1)),
        ("-1y", False, "2020-11-13", datetime.date(year=2019, month=1, day=1)),
        # One difference end
        ("+1d", True, "2020-11-13", datetime.date(year=2020, month=11, day=14)),
        ("-1d", True, "2020-11-13", datetime.date(year=2020, month=11, day=12)),
        ("+1w", True, "2020-11-13", datetime.date(year=2020, month=11, day=22)),
        ("-1w", True, "2020-11-13", datetime.date(year=2020, month=11, day=8)),
        ("+1m", True, "2020-11-13", datetime.date(year=2020, month=12, day=31)),
        ("-1m", True, "2020-11-13", datetime.date(year=2020, month=10, day=31)),
        ("+1y", True, "2020-11-13", datetime.date(year=2021, month=12, day=31)),
        ("-1y", True, "2020-11-13", datetime.date(year=2019, month=12, day=31)),
        # One difference start, year boundary
        ("+1d", False, "2020-12-31", datetime.date(year=2021, month=1, day=1)),
        ("+1w", False, "2020-12-31", datetime.date(year=2021, month=1, day=4)),
        ("+1m", False, "2020-12-31", datetime.date(year=2021, month=1, day=1)),
        ("+1y", False, "2020-12-31", datetime.date(year=2021, month=1, day=1)),
        # One difference end, year boundary
        ("+1d", True, "2020-12-31", datetime.date(year=2021, month=1, day=1)),
        ("+1w", True, "2020-12-31", datetime.date(year=2021, month=1, day=10)),
        ("+1m", True, "2020-12-31", datetime.date(year=2021, month=1, day=31)),
        ("+1y", True, "2020-12-31", datetime.date(year=2021, month=12, day=31)),
        # One difference start, year boundary
        ("-1d", False, "2021-1-1", datetime.date(year=2020, month=12, day=31)),
        ("-1w", False, "2021-1-1", datetime.date(year=2020, month=12, day=21)),
        # ("-1m", False, "2021-1-1", datetime.date(year=2020, month=12, day=1)),
        ("-1y", False, "2021-1-1", datetime.date(year=2020, month=1, day=1)),
        # One difference end, year boundary
        ("-1d", True, "2021-1-1", datetime.date(year=2020, month=12, day=31)),
        ("-1w", True, "2021-1-1", datetime.date(year=2020, month=12, day=27)),
        # ("-1m", True, "2021-1-1", datetime.date(year=2020, month=12, day=31)),
        ("-1y", True, "2021-1-1", datetime.date(year=2020, month=12, day=31)),
    ),
)
def test_parse_filter_date(input_string, end_date, frozen_date, expected_date):
    with freeze_time(frozen_date):
        assert parse_maybe_relative_date_string(input_string, end_date) == expected_date
