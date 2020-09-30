import json
import os
from datetime import date, datetime, time

import pytest
from django.core.management import call_command
from django_orghierarchy.models import Organization

from hours.models import (
    DailyHours,
    DataSource,
    Opening,
    Period,
    Target,
    TargetIdentifier,
    TargetType,
)
from hours.tests.utils import check_opening_hours


def parse_date(date: str) -> date:
    date = datetime.strptime(date, "%Y-%m-%d").date()
    return date


def parse_time(time: str) -> time:
    time = datetime.strptime(time, "%H:%M").time()
    return time


def check_opening_hours_from_file(test_file_name):
    # Check that all opening hours were saved
    test_data = []
    test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
    with open(test_file_path) as f:
        test_data = json.load(f)["data"]
    check_opening_hours(test_data)


@pytest.fixture
def mock_tprek_data(requests_mock):
    test_file_name = "test_import_tprek_data.json"
    test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
    with open(test_file_path) as f:
        mock_data = f.read()
        requests_mock.get(
            "http://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=mock_data
        )
    call_command("hours_import", "tprek", "--all")
    with open(test_file_path) as f:
        return json.load(f)[0]


@pytest.mark.django_db
@pytest.fixture
def get_mock_library_data(mock_tprek_data, requests_mock):
    def _mock_library_data(test_file_name):
        # Call the library importer for the single created library
        kallio = Target.objects.all()[0]
        kallio_kirkanta_id = kallio.identifiers.get(data_source="kirkanta").origin_id
        print(kallio_kirkanta_id)
        url_to_mock = (
            "https://api.kirjastot.fi/v4/library/%s/"
            "?with=schedules&period.start=2020-06-01&period.end=2021-07-01"
            % kallio_kirkanta_id
        )
        test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
        print(url_to_mock)
        with open(test_file_path) as f:
            mock_data = f.read()
            requests_mock.get(url_to_mock, text=mock_data)
        call_command(
            "hours_import",
            "kirjastot",
            "--openings",
            "--single",
            kallio.id,
            "--date",
            "2020-07-15",
        )

    return _mock_library_data


@pytest.mark.django_db
def test_import_tprek(mock_tprek_data):
    # Check created objects
    assert Target.objects.count() == 1
    assert DataSource.objects.count() == 3
    assert Organization.objects.count() == 1
    assert TargetIdentifier.objects.count() == 2

    # Also check the fields are imported correctly
    kallio = Target.objects.all()[0]
    assert kallio.data_source_id == "tprek"
    assert kallio.origin_id == str(mock_tprek_data["id"])
    assert kallio.name == mock_tprek_data["name_fi"]
    assert kallio.organization_id == "tprek:%s" % mock_tprek_data["dept_id"]
    assert (
        kallio.same_as
        == "http://www.hel.fi/palvelukarttaws/rest/v4/unit/%s/" % mock_tprek_data["id"]
    )
    assert kallio.target_type == TargetType.UNIT
    identifiers = {x.data_source_id: x for x in kallio.identifiers.all()}
    for source in mock_tprek_data["sources"]:
        assert source["source"] in identifiers
        assert identifiers[source["source"]].origin_id == source["id"]


@pytest.mark.django_db
def test_import_kirjastot_simple(get_mock_library_data, mock_tprek_data):
    test_file_name = "test_import_kirjastot_data_simple.json"
    get_mock_library_data(test_file_name)

    # Check created objects
    assert Period.objects.count() == 1
    assert Opening.objects.count() == 12
    assert DailyHours.objects.count() == 12

    # Check daily opening hours
    check_opening_hours_from_file(test_file_name)


@pytest.mark.django_db
def test_import_kirjastot_complex(get_mock_library_data, mock_tprek_data):
    test_file_name = "test_import_kirjastot_data_complex.json"
    get_mock_library_data(test_file_name)

    # Check created objects
    assert Period.objects.count() == 2
    periods_by_start = Period.objects.order_by("period")
    summer_period, midsummer_period = periods_by_start
    assert summer_period.openings.count() == 46
    assert midsummer_period.openings.count() == 5

    # Check daily opening hours
    check_opening_hours_from_file(test_file_name)


@pytest.mark.django_db
def test_import_kirjastot_pattern(get_mock_library_data, mock_tprek_data):
    test_file_name = "test_import_kirjastot_data_pattern.json"
    get_mock_library_data(test_file_name)

    # Check created objects
    assert Period.objects.count() == 2
    periods_by_start = Period.objects.order_by("period")
    summer_period, midsummer_period = periods_by_start
    assert summer_period.openings.count() == 36
    assert midsummer_period.openings.count() == 5

    # Check daily opening hours
    check_opening_hours_from_file(test_file_name)


# @pytest.mark.django_db
# def test_import_kirjastot_update(get_mock_library_data, mock_tprek_data,
#                                  requests_mock):
#     test_file_name = 'test_import_kirjastot_data_simple.json'
#     get_mock_library_data(test_file_name)

#     # Check daily opening hours
#     check_opening_hours_from_file(test_file_name)

#     # Change the imported data bounds (as will happen at change of month)
#     # Ensure the periods are updated sensibly
#     #test_file_name = 'test_import_kirjastot_data_changed.json'
#     #get_mock_library_data(test_file_name)

#     # Check daily opening hours again
#     #check_all_opening_hours(test_file_name, kallio)
#     assert False
