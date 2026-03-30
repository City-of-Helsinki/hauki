"""Tests for the ResourceViewSet prefetch optimization that prevents N+1 queries
in the ``opening_hours`` and ``is_open_now`` actions."""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from hours.enums import State, Weekday


def _make_authenticated_client(user_factory):
    """Return an APIClient using force_authenticate to avoid session-query noise."""
    user = user_factory(is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _capture_query_count(client, url, params=None):
    """Perform a GET and return (status_code, query_count, response)."""
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url, params or {})
    return response.status_code, len(ctx.captured_queries), response


def _create_open_period(
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    *,
    start_date,
    end_date,
    start_time=datetime.time(8, 0),
    end_time=datetime.time(16, 0),
    name=None,
    **ts_kwargs,
):
    """Create a DatePeriod with one TimeSpanGroup and one open TimeSpan.

    Returns *(period, time_span_group)*; extra kwargs go to ``time_span_factory``.
    """
    period = date_period_factory(
        resource=resource,
        name=name or "Test period",
        start_date=start_date,
        end_date=end_date,
    )
    tsg = time_span_group_factory(period=period)
    time_span_factory(
        group=tsg,
        start_time=start_time,
        end_time=end_time,
        resource_state=State.OPEN,
        **ts_kwargs,
    )
    return period, tsg


def _fetch_opening_hours(client, resource, date, end_date=None):
    """GET the resource opening-hours endpoint for the given date range.

    ``end_date`` defaults to ``date`` (single-day query).
    """
    url = reverse("resource-opening-hours", kwargs={"pk": resource.id})
    return client.get(url, {"start_date": str(date), "end_date": str(end_date or date)})


@pytest.mark.django_db
def test_resource_opening_hours_action_returns_correct_data(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    today = datetime.date(2024, 6, 1)
    _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        name="Test period one",
        start_date=today,
        end_date=today + datetime.timedelta(days=30),
    )

    with freeze_time("2024-06-01 10:00:00+03:00"):
        response = _fetch_opening_hours(admin_client, resource, today)

    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert response.data[0]["date"] == str(today)
    assert len(response.data[0]["times"]) == 1
    assert response.data[0]["times"][0]["start_time"] == "08:00:00"
    assert response.data[0]["times"][0]["end_time"] == "16:00:00"


@pytest.mark.django_db
def test_resource_opening_hours_action_with_multiple_date_periods(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    today = datetime.date(2024, 6, 1)

    for hour_start in [8, 18]:
        _create_open_period(
            resource,
            date_period_factory,
            time_span_group_factory,
            time_span_factory,
            start_date=today,
            end_date=today + datetime.timedelta(days=30),
            start_time=datetime.time(hour_start, 0),
            end_time=datetime.time(hour_start + 2, 0),
        )

    with freeze_time("2024-06-01 10:00:00+03:00"):
        response = _fetch_opening_hours(admin_client, resource, today)

    assert response.status_code == 200, response.data
    assert len(response.data[0]["times"]) == 2


@pytest.mark.django_db
def test_resource_opening_hours_action_with_rules(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    today = datetime.date(2024, 6, 3)  # Monday
    _, tsg = _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        start_date=today,
        end_date=today + datetime.timedelta(days=30),
        start_time=datetime.time(9, 0),
        end_time=datetime.time(17, 0),
        weekdays=[Weekday.MONDAY],
    )
    rule_factory(
        group=tsg,
        context="period",
        subject="week",
        frequency_ordinal=None,
        frequency_modifier="even",
    )

    with freeze_time("2024-06-03 10:00:00+03:00"):
        response = _fetch_opening_hours(
            admin_client,
            resource,
            today,
            end_date=today + datetime.timedelta(days=13),
        )

    assert response.status_code == 200, response.data


@pytest.mark.parametrize(
    "url_name,params",
    [
        pytest.param(
            "resource-opening-hours",
            {"start_date": "2024-06-03", "end_date": "2024-06-10"},
            id="opening_hours",
        ),
        pytest.param(
            "resource-is-open-now",
            {},
            id="is_open_now",
        ),
    ],
)
@pytest.mark.django_db
def test_query_count_constant_across_date_periods(
    url_name,
    params,
    user_factory,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
    rule_factory,
):
    """Query count must stay the same whether the resource has 1 or 3 DatePeriods
    (each with a TimeSpanGroup, TimeSpan, and Rule). A regression here indicates
    the prefetch_related optimization is no longer effective."""
    client = _make_authenticated_client(user_factory)
    today = datetime.date(2024, 6, 3)  # Monday
    url = reverse(url_name, kwargs={"pk": resource.id})

    _, tsg1 = _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        start_date=today,
        end_date=today + datetime.timedelta(days=60),
    )
    rule_factory(group=tsg1, context="period", subject="week")

    with freeze_time("2024-06-03 12:00:00+03:00"):
        status_1, count_1_period, resp1 = _capture_query_count(client, url, params)
    assert status_1 == 200, resp1.data

    for _ in range(2):
        _, tsg = _create_open_period(
            resource,
            date_period_factory,
            time_span_group_factory,
            time_span_factory,
            start_date=today,
            end_date=today + datetime.timedelta(days=60),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(18, 0),
        )
        rule_factory(group=tsg, context="period", subject="week")

    with freeze_time("2024-06-03 12:00:00+03:00"):
        status_3, count_3_periods, resp3 = _capture_query_count(client, url, params)
    assert status_3 == 200, resp3.data

    assert count_1_period == count_3_periods, (
        f"N+1 detected: {count_3_periods} queries for 3 date periods vs "
        f"{count_1_period} queries for 1 date period. "
        f"The prefetch_related optimisation for {url_name!r} may not be working."
    )


@pytest.mark.django_db
def test_resource_is_open_now_action_with_prefetch(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    today = datetime.date(2024, 6, 3)  # Monday
    _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        name="Test period",
        start_date=today,
        end_date=today + datetime.timedelta(days=30),
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2024-06-03 12:00:00+03:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, response.data
    assert response.data["is_open"] is True
    assert len(response.data["matching_opening_hours"]) == 1


@pytest.mark.django_db
def test_resource_opening_hours_includes_date_period_with_null_end_date(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    """Periods with end_date=None pass the Q(end_date__isnull=True) prefetch
    filter and must appear in the opening hours response."""
    today = datetime.date(2024, 6, 1)
    _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        name="Open-ended period",
        start_date=today - datetime.timedelta(days=30),
        end_date=None,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(17, 0),
    )

    with freeze_time("2024-06-01 10:00:00+03:00"):
        response = _fetch_opening_hours(admin_client, resource, today)

    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert len(response.data[0]["times"]) >= 1


@pytest.mark.django_db
def test_resource_opening_hours_excludes_date_periods_beyond_26h_cutoff(
    user_factory,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    """Periods with end_date older than (now − 26 h) are excluded by the prefetch
    filter and must not contribute opening hours to the response."""
    client = _make_authenticated_client(user_factory)

    # Freeze at noon so that "now - 26 h" is safely into yesterday.
    with freeze_time("2024-06-04 12:00:00+00:00"):
        today = timezone.now().date()
        three_days_ago = today - datetime.timedelta(days=3)

        # Old period – excluded by the 26-hour prefetch filter
        _create_open_period(
            resource,
            date_period_factory,
            time_span_group_factory,
            time_span_factory,
            start_date=three_days_ago - datetime.timedelta(days=10),
            end_date=three_days_ago,
            start_time=datetime.time(0, 0),
            end_time=datetime.time(23, 59),
        )

        # Current period – included by the prefetch filter
        _create_open_period(
            resource,
            date_period_factory,
            time_span_group_factory,
            time_span_factory,
            start_date=today,
            end_date=today + datetime.timedelta(days=30),
        )

        response = _fetch_opening_hours(client, resource, today)

    assert response.status_code == 200, response.data
    times = response.data[0]["times"]
    # Only the current period's 08:00–16:00 span should appear.
    assert len(times) == 1, (
        f"Expected 1 time span (from the current period) but got {len(times)}: {times}"
    )
    assert times[0]["start_time"] == "08:00:00"
    assert times[0]["end_time"] == "16:00:00"


@pytest.mark.django_db
def test_resource_is_open_now_includes_date_period_with_null_end_date(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    """Periods with end_date=None pass the prefetch filter and must be considered
    by is_open_now when reporting whether the resource is open."""
    today = datetime.date(2024, 6, 3)
    _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        name="Open-ended period",
        start_date=today - datetime.timedelta(days=30),
        end_date=None,
    )

    url = reverse("resource-is-open-now", kwargs={"pk": resource.id})

    with freeze_time("2024-06-03 12:00:00+03:00"):
        response = admin_client.get(url)

    assert response.status_code == 200, response.data
    assert response.data["is_open"] is True


@pytest.mark.django_db
def test_resource_opening_hours_returns_historical_date_periods(
    admin_client,
    resource,
    date_period_factory,
    time_span_group_factory,
    time_span_factory,
):
    """Querying opening_hours for a past date range must include date periods
    whose end_date is far before the current time.  Previously, the prefetch
    filter used timezone.now() as its cutoff, silently excluding any period
    that had already ended."""
    historical_start = datetime.date(2023, 3, 1)
    historical_end = datetime.date(2023, 3, 31)

    _create_open_period(
        resource,
        date_period_factory,
        time_span_group_factory,
        time_span_factory,
        start_date=historical_start,
        end_date=historical_end,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(17, 0),
    )

    # "Now" is far in the future relative to the period.
    with freeze_time("2026-03-31 12:00:00+03:00"):
        response = _fetch_opening_hours(
            admin_client, resource, historical_start, end_date=historical_end
        )

    assert response.status_code == 200, response.data
    assert len(response.data) > 0, (
        "Expected opening hours for the historical range but got none — "
        "the prefetch filter may be incorrectly using timezone.now() "
        "instead of the requested start_date."
    )
    # Verify at least one day has the expected 09:00–17:00 span
    first_day_times = response.data[0]["times"]
    assert len(first_day_times) >= 1
    assert first_day_times[0]["start_time"] == "09:00:00"
    assert first_day_times[0]["end_time"] == "17:00:00"
