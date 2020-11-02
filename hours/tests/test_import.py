import json
import os

import pytest
from django.core.management import call_command
from django_orghierarchy.models import Organization

from hours.models import DataSource, Resource, ResourceOrigin, ResourceType

# from datetime import date, datetime, time


# from hours.tests.utils import check_opening_hours


# def parse_date(date: str) -> date:
#     date = datetime.strptime(date, "%Y-%m-%d").date()
#     return date


# def parse_time(time: str) -> time:
#     time = datetime.strptime(time, "%H:%M").time()
#     return time


# def check_opening_hours_from_file(test_file_name):
#     # Check that all opening hours were saved
#     test_data = []
#     test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
#     with open(test_file_path) as f:
#         test_data = json.load(f)["data"]
#     check_opening_hours(test_data)


@pytest.fixture
def mock_tprek_data(requests_mock, request):
    units_file_name = "test_import_tprek_units.json"
    connections_file_name = "test_import_tprek_connections.json"
    units_file_path = os.path.join(os.path.dirname(__file__), units_file_name)
    connections_file_path = os.path.join(
        os.path.dirname(__file__), connections_file_name
    )
    with open(units_file_path) as units_file, open(
        connections_file_path
    ) as connections_file:
        requests_mock.get(
            "http://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=units_file.read()
        )
        requests_mock.get(
            "http://www.hel.fi/palvelukarttaws/rest/v4/connection/",
            text=connections_file.read(),
        )
    if request.param:
        call_command("hours_import", "tprek", resources=True, merge=True)
    else:
        call_command("hours_import", "tprek", resources=True)
    with open(units_file_path) as units_file, open(
        connections_file_path
    ) as connections_file:
        return {
            "merged_identical_resources": request.param,
            "units": json.load(units_file),
            "connections": json.load(connections_file),
        }


# @pytest.mark.django_db
# @pytest.fixture
# def get_mock_library_data(mock_tprek_data, requests_mock):
#     def _mock_library_data(test_file_name):
#         # Call the library importer for the single created library
#         kallio = Target.objects.all()[0]
#         kallio_kirkanta_id = kallio.identifiers.get(data_source="kirkanta").origin_id
#         print(kallio_kirkanta_id)
#         url_to_mock = (
#             "https://api.kirjastot.fi/v4/library/%s/"
#             "?with=schedules&period.start=2020-06-01&period.end=2021-07-01"
#             % kallio_kirkanta_id
#         )
#         test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
#         print(url_to_mock)
#         with open(test_file_path) as f:
#             mock_data = f.read()
#             requests_mock.get(url_to_mock, text=mock_data)
#         call_command(
#             "hours_import",
#             "kirjastot",
#             "--openings",
#             "--single",
#             kallio.id,
#             "--date",
#             "2020-07-15",
#         )

#     return _mock_library_data


@pytest.mark.django_db
@pytest.mark.parametrize("mock_tprek_data", [False, True], indirect=True)
def test_import_tprek(mock_tprek_data):
    # The results should depend on whether we merge identical connections
    merge = mock_tprek_data["merged_identical_resources"]

    # Check created objects
    expected_n_resources = 16 if merge else 21
    assert Resource.objects.count() == expected_n_resources
    assert DataSource.objects.count() == 3
    assert Organization.objects.count() == 1
    assert ResourceOrigin.objects.count() == 25

    # Check the units are imported correctly
    kallio, oodi = Resource.objects.filter(resource_type=ResourceType.UNIT)
    mock_kallio, mock_oodi = mock_tprek_data["units"]
    assert kallio.name_fi == mock_kallio["name_fi"]
    assert kallio.name_sv == mock_kallio["name_sv"]
    assert kallio.name_en == mock_kallio["name_en"]
    assert kallio.address_fi.startswith(mock_kallio["street_address_fi"])
    assert kallio.address_sv.startswith(mock_kallio["street_address_sv"])
    assert kallio.address_en.startswith(mock_kallio["street_address_en"])
    assert kallio.address_fi.endswith(mock_kallio["address_city_fi"])
    assert kallio.address_sv.endswith(mock_kallio["address_city_sv"])
    assert kallio.address_en.endswith(mock_kallio["address_city_en"])
    assert oodi.description_fi == mock_oodi["desc_fi"]
    assert oodi.description_sv == mock_oodi["desc_sv"]
    assert oodi.description_en == mock_oodi["desc_en"]
    assert kallio.organization_id == "tprek:%s" % mock_kallio["dept_id"]
    assert kallio.resource_type == ResourceType.UNIT
    assert (
        kallio.extra_data["citizen_url"]
        == "https://palvelukartta.hel.fi/fi/unit/%s" % mock_kallio["id"]
    )
    origins = {x.data_source_id: x for x in kallio.origins.all()}
    assert "tprek" in origins
    assert origins["tprek"].origin_id == str(mock_kallio["id"])
    for source in mock_kallio["sources"]:
        if source["source"] == "internal":
            assert kallio.extra_data["admin_url"] == (
                "https://asiointi.hel.fi/tprperhe/TPR/UI/ServicePoint"
                "/ServicePointEdit/%s" % source["id"]
            )
        else:
            assert source["source"] in origins
            assert origins[source["source"]].origin_id == source["id"]

    # Check the right connections are under the right units
    if merge:

        (
            covid,
            snack,
            afternoon,
            berth,
            space,
            support,
        ) = Resource.objects.filter(resource_type=ResourceType.SUBSECTION)
        assert {covid, snack, afternoon, berth, space} == set(
            kallio.children.filter(resource_type=ResourceType.SUBSECTION)
        )
        assert {covid, snack, berth, space, support} == set(
            oodi.children.filter(resource_type=ResourceType.SUBSECTION)
        )

        (
            reservations,
            directorkallio,
            directoroodi,
        ) = Resource.objects.filter(resource_type=ResourceType.CONTACT)
        assert {reservations, directorkallio} == set(
            kallio.children.filter(resource_type=ResourceType.CONTACT)
        )
        assert {reservations, directoroodi} == set(
            oodi.children.filter(resource_type=ResourceType.CONTACT)
        )

    else:

        (
            covid1,
            covid2,
            snack1,
            snack2,
            afternoon,
            berth1,
            berth2,
            space1,
            space2,
            support,
        ) = Resource.objects.filter(resource_type=ResourceType.SUBSECTION)
        assert {covid1, snack1, afternoon, berth1, space1} == set(
            kallio.children.filter(resource_type=ResourceType.SUBSECTION)
        )
        assert {covid2, snack2, berth2, space2, support} == set(
            oodi.children.filter(resource_type=ResourceType.SUBSECTION)
        )

        (
            reservations1,
            reservations2,
            directorkallio,
            directoroodi,
        ) = Resource.objects.filter(resource_type=ResourceType.CONTACT)
        assert {reservations1, directorkallio} == set(
            kallio.children.filter(resource_type=ResourceType.CONTACT)
        )
        assert {reservations2, directoroodi} == set(
            oodi.children.filter(resource_type=ResourceType.CONTACT)
        )

    (
        hydrobic,
        reservations,
        exercise,
    ) = Resource.objects.filter(resource_type=ResourceType.ONLINE_SERVICE)
    assert set() == set(
        kallio.children.filter(resource_type=ResourceType.ONLINE_SERVICE)
    )
    assert {hydrobic, reservations, exercise} == set(
        oodi.children.filter(resource_type=ResourceType.ONLINE_SERVICE)
    )

    (mikkolankuja, floorantie) = Resource.objects.filter(
        resource_type=ResourceType.ENTRANCE
    )
    assert {mikkolankuja} == set(
        kallio.children.filter(resource_type=ResourceType.ENTRANCE)
    )
    assert {floorantie} == set(
        oodi.children.filter(resource_type=ResourceType.ENTRANCE)
    )


# @pytest.mark.django_db
# def test_import_kirjastot_simple(get_mock_library_data, mock_tprek_data):
#     test_file_name = "test_import_kirjastot_data_simple.json"
#     get_mock_library_data(test_file_name)

#     # Check created objects
#     assert Period.objects.count() == 1
#     assert Opening.objects.count() == 12
#     assert DailyHours.objects.count() == 12

#     # Check daily opening hours
#     check_opening_hours_from_file(test_file_name)


# @pytest.mark.django_db
# def test_import_kirjastot_complex(get_mock_library_data, mock_tprek_data):
#     test_file_name = "test_import_kirjastot_data_complex.json"
#     get_mock_library_data(test_file_name)

#     # Check created objects
#     assert Period.objects.count() == 2
#     periods_by_start = Period.objects.order_by("period")
#     summer_period, midsummer_period = periods_by_start
#     assert summer_period.openings.count() == 46
#     assert midsummer_period.openings.count() == 5

#     # Check daily opening hours
#     check_opening_hours_from_file(test_file_name)


# @pytest.mark.django_db
# def test_import_kirjastot_pattern(get_mock_library_data, mock_tprek_data):
#     test_file_name = "test_import_kirjastot_data_pattern.json"
#     get_mock_library_data(test_file_name)

#     # Check created objects
#     assert Period.objects.count() == 2
#     periods_by_start = Period.objects.order_by("period")
#     summer_period, midsummer_period = periods_by_start
#     assert summer_period.openings.count() == 36
#     assert midsummer_period.openings.count() == 5

#     # Check daily opening hours
#     check_opening_hours_from_file(test_file_name)


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
