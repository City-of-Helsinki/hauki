import json
import os

import pytest
from django.core.management import call_command
from django_orghierarchy.models import Organization

from hours.models import (
    DataSource,
    DatePeriod,
    Resource,
    ResourceOrigin,
    ResourceType,
    Rule,
    TimeSpan,
    TimeSpanGroup,
)

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
    if hasattr(request, "param"):
        change = request.param["change"]
        merge = request.param["merge"]
    else:
        change = None
        merge = False
    units_file_name = "test_import_tprek_units.json"
    connections_file_name = "test_import_tprek_connections.json"
    units_file_path = os.path.join(
        os.path.dirname(__file__), "fixtures", units_file_name
    )
    connections_file_path = os.path.join(
        os.path.dirname(__file__), "fixtures", connections_file_name
    )
    with open(units_file_path) as units_file, open(
        connections_file_path
    ) as connections_file:
        units = json.load(units_file)
        connections = json.load(connections_file)
    requests_mock.get(
        "http://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=json.dumps(units)
    )
    requests_mock.get(
        "http://www.hel.fi/palvelukarttaws/rest/v4/connection/",
        text=json.dumps(connections),
    )
    if merge:
        call_command("hours_import", "tprek", resources=True, merge=True)
        print("merged identical resources")
    else:
        call_command("hours_import", "tprek", resources=True)
    if change == "edit":
        # Modify one connection that is already imported duplicated.
        # Two single connections should appear.
        connections[6]["name_fi"] = "Välipala peruttu"
    if change == "remove":
        # Remove one connection that is already imported duplicated.
        # Duplicated connection should become single.
        connections.pop(8)
    if change == "add":
        # Add one connection that is not yet imported duplicated.
        # Single connection should become duplicated.
        connections.append(
            {
                "id": 28,
                "unit_id": 8215,
                "section_type": "ESERVICE_LINK",
                "name_fi": "Ohjattuun liikuntaan ilmoittautuminen",
                "www_fi": "https://resurssivaraus.espoo.fi/ohjattuliikunta/haku",
            }
        )
    if change:
        requests_mock.get(
            "http://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=json.dumps(units)
        )
        requests_mock.get(
            "http://www.hel.fi/palvelukarttaws/rest/v4/connection/",
            text=json.dumps(connections),
        )
        if merge:
            call_command("hours_import", "tprek", resources=True, merge=True)
            print("merged identical resources")
        else:
            call_command("hours_import", "tprek", resources=True)
        print("made a change and rerun")
        print(change)
    return {
        "merged_identical_resources": merge,
        "made_a_change_and_rerun": change,
        "units": units,
        "connections": connections,
    }


@pytest.mark.django_db
@pytest.fixture
def get_mock_library_data(mock_tprek_data, requests_mock):
    def _mock_library_data(test_file_name):
        kallio_tprek_id = 8215
        kallio = Resource.objects.get(
            origins__data_source="tprek", origins__origin_id=kallio_tprek_id
        )
        # Call the library importer for Kallio
        kallio_kirkanta_id = kallio.origins.get(data_source="kirkanta").origin_id
        url_to_mock = (
            "https://api.kirjastot.fi/v4/library/%s/?with=schedules"
            "&refs=period&period.start=2020-06-01&period.end=2021-06-01"
            % kallio_kirkanta_id
        )
        print(url_to_mock)
        test_file_path = os.path.join(
            os.path.dirname(__file__), "fixtures", test_file_name
        )
        with open(test_file_path) as f:
            mock_data = f.read()
            requests_mock.get(url_to_mock, text=mock_data)
        call_command(
            "hours_import",
            "kirjastot",
            "--openings",
            "--single",
            kallio_kirkanta_id,
            "--date",
            "2020-06-15",
        )

    return _mock_library_data


parameters = []
for merge in [False, True]:
    for change in [None, "edit", "remove", "add"]:
        parameters.append({"merge": merge, "change": change})


@pytest.mark.django_db
@pytest.mark.parametrize("mock_tprek_data", parameters, indirect=True)
def test_import_tprek(mock_tprek_data):
    # The results should depend on whether we merge identical connections
    # and whether we have changed the connections and rerun the import
    merge = mock_tprek_data["merged_identical_resources"]
    change = mock_tprek_data["made_a_change_and_rerun"]

    # Check created objects
    if change == "add":
        expected_n_resources = 22
    elif change == "remove":
        expected_n_resources = 20
    else:
        expected_n_resources = 21
    if change == "edit":
        expected_n_merged_resources = 17
    else:
        expected_n_merged_resources = 16
    if not merge:
        assert Resource.objects.count() == expected_n_resources
    else:
        assert Resource.objects.count() == expected_n_merged_resources
    assert DataSource.objects.count() == 3
    assert Organization.objects.count() == 1
    external_origins = 4
    if change == "remove" and not merge:
        # if a resource is soft deleted, its origin will remain.
        # if it was merged, extra origin will be deleted.
        old_origins = 1
    else:
        old_origins = 0
    assert (
        ResourceOrigin.objects.count()
        == expected_n_resources + external_origins + old_origins
    )

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
    subsections = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.SUBSECTION
    )
    contacts = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.CONTACT
    )
    online_services = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.ONLINE_SERVICE
    )
    entrances = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.ENTRANCE
    )

    # Check subsections
    if merge:
        if change == "edit":
            # snack changed in kallio
            (covid, snack1, afternoon, berth, space, support, snack2) = subsections
            subsections_expected_in_kallio = {covid, snack2, afternoon, berth, space}
            subsections_expected_in_oodi = {covid, snack1, berth, space, support}
        else:
            (covid, snack, afternoon, berth, space, support) = subsections
            subsections_expected_in_kallio = {covid, snack, afternoon, berth, space}
            subsections_expected_in_oodi = {covid, snack, berth, space, support}
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
        ) = subsections
        subsections_expected_in_kallio = {covid1, snack1, afternoon, berth1, space1}
        subsections_expected_in_oodi = {covid2, snack2, berth2, space2, support}

    assert subsections_expected_in_kallio == set(
        kallio.children.filter(resource_type=ResourceType.SUBSECTION)
    )
    assert subsections_expected_in_oodi == set(
        oodi.children.filter(resource_type=ResourceType.SUBSECTION)
    )

    # Check contacts
    if merge:
        (reservations, directorkallio, directoroodi) = contacts
        if change == "remove":
            # reservations removed in kallio
            contacts_expected_in_kallio = {directorkallio}
        else:
            contacts_expected_in_kallio = {reservations, directorkallio}
        contacts_expected_in_oodi = {reservations, directoroodi}
    else:
        if change == "remove":
            # reservations removed in kallio
            (reservations2, directorkallio, directoroodi) = contacts
            contacts_expected_in_kallio = {directorkallio}
        else:
            (reservations1, reservations2, directorkallio, directoroodi) = contacts
            contacts_expected_in_kallio = {reservations1, directorkallio}
        contacts_expected_in_oodi = {reservations2, directoroodi}

    assert contacts_expected_in_kallio == set(
        kallio.children.filter(resource_type=ResourceType.CONTACT)
    )
    assert contacts_expected_in_oodi == set(
        oodi.children.filter(resource_type=ResourceType.CONTACT)
    )

    # Check online services
    if merge:
        (hydrobic, reservations, exercise) = online_services
        if change == "add":
            # exercise added to kallio
            online_services_expected_in_kallio = {exercise}
        else:
            online_services_expected_in_kallio = set()
        online_services_expected_in_oodi = {hydrobic, reservations, exercise}
    else:
        if change == "add":
            # exercise added to kallio
            (hydrobic, reservations, exercise1, exercise2) = online_services
            online_services_expected_in_kallio = {exercise2}
        else:
            (hydrobic, reservations, exercise1) = online_services
            online_services_expected_in_kallio = set()
        online_services_expected_in_oodi = {hydrobic, reservations, exercise1}

    assert online_services_expected_in_kallio == set(
        kallio.children.filter(resource_type=ResourceType.ONLINE_SERVICE)
    )
    assert online_services_expected_in_oodi == set(
        oodi.children.filter(resource_type=ResourceType.ONLINE_SERVICE)
    )

    # Check entrances
    (mikkolankuja, floorantie) = entrances
    assert {mikkolankuja} == set(
        kallio.children.filter(resource_type=ResourceType.ENTRANCE)
    )
    assert {floorantie} == set(
        oodi.children.filter(resource_type=ResourceType.ENTRANCE)
    )


@pytest.mark.django_db
def test_import_kirjastot_simple(get_mock_library_data, mock_tprek_data):
    test_file_name = "test_import_kirjastot_data_simple.json"
    get_mock_library_data(test_file_name)

    # Check created objects
    assert DatePeriod.objects.count() == 1
    assert TimeSpan.objects.count() == 5
    assert TimeSpanGroup.objects.count() == 1
    # Simple data should have pattern repeating weekly
    assert Rule.objects.count() == 0


@pytest.mark.django_db
def test_import_kirjastot_complex(get_mock_library_data, mock_tprek_data):
    test_file_name = "test_import_kirjastot_data_complex.json"
    get_mock_library_data(test_file_name)

    # Check created objects
    assert DatePeriod.objects.count() == 5
    periods_by_start = DatePeriod.objects.order_by("start_date")
    (
        summer_period,
        midsummer_pre_eve,
        midsummer_eve,
        midsummer_sat,
        midsummer_sun,
    ) = periods_by_start
    assert summer_period.time_span_groups.count() == 20
    assert midsummer_pre_eve.time_span_groups.count() == 1
    assert midsummer_eve.time_span_groups.count() == 0
    assert midsummer_sat.time_span_groups.count() == 0
    assert midsummer_sun.time_span_groups.count() == 0
    # Complex data should have rules for each weekly time span
    assert Rule.objects.count() == 20


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
