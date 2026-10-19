import copy
import json
import os
from datetime import datetime, timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
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
    with (
        open(units_file_path) as units_file,
        open(connections_file_path) as connections_file,
    ):
        units = json.load(units_file)
        connections = json.load(connections_file)
    requests_mock.get(
        "https://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=json.dumps(units)
    )
    requests_mock.get(
        "https://www.hel.fi/palvelukarttaws/rest/v4/connection/",
        text=json.dumps(connections),
    )
    if merge:
        call_command("hours_import", "tprek", resources=True, merge=True)
        print("merged specified connections")  # noqa: T201
    else:
        call_command("hours_import", "tprek", resources=True)
    if change == "edit":
        # Modify one connection that is already imported duplicated.
        # Two single connections should appear.
        connections[8]["name_fi"] = "Venepaikkavaraukset täällä nyt eri tavalla"
    if change == "remove":
        # Remove one connection that is already imported duplicated.
        # Duplicated connection should become single.
        connections.pop(8)
    if change == "add":
        # Add one connection that is not yet imported duplicated.
        # Single connection should become duplicated.
        connections.append(
            {
                "connection_id": "contact-100",
                "unit_id": 8215,
                "section_type": "ESERVICE_LINK",
                "name_fi": "Ohjattuun liikuntaan ilmoittautuminen",
                "www_fi": "https://resurssivaraus.espoo.fi/ohjattuliikunta/haku",
            }
        )
    if change:
        requests_mock.get(
            "https://www.hel.fi/palvelukarttaws/rest/v4/unit/", text=json.dumps(units)
        )
        requests_mock.get(
            "https://www.hel.fi/palvelukarttaws/rest/v4/connection/",
            text=json.dumps(connections),
        )
        if merge:
            call_command("hours_import", "tprek", resources=True, merge=True)
            print("merged specified connections")  # noqa: T201
        else:
            call_command("hours_import", "tprek", resources=True)
        print("made a change and rerun")  # noqa: T201
        print(change)  # noqa: T201
    return {
        "merged_specific_connections": merge,
        "made_a_change_and_rerun": change,
        "units": units,
        "connections": connections,
    }


@pytest.fixture
def mock_library_data(requests_mock, request):
    # We should have the same hours whether base period is endless or ends next year
    endless = request.param["endless"]
    # The results should depend on possible changes done to period
    change = request.param["change"]

    def _mock_library_data(test_file_name):
        kirkanta = DataSource.objects.create(id="kirkanta")
        kallio_kirkanta_id = 84860
        kallio = Resource.objects.create()
        ResourceOrigin.objects.create(
            data_source=kirkanta, origin_id=kallio_kirkanta_id, resource=kallio
        )
        # Call the library importer for Kallio
        date = "2020-06-01"
        url_to_mock = (
            f"https://api.kirjastot.fi/v4/library/{kallio_kirkanta_id}/?with=schedules"
            "&refs=period&period.start=2020-06-01&period.end=2021-06-01"
        )
        test_file_path = os.path.join(
            os.path.dirname(__file__), "fixtures", test_file_name
        )
        with open(test_file_path) as f:
            mock_data = json.load(f)

        period_ids = iter(mock_data["refs"]["period"])
        base_period_id = next(period_ids)
        if endless:
            mock_data["refs"]["period"][base_period_id]["validUntil"] = None
        requests_mock.get(url_to_mock, text=json.dumps(mock_data))
        call_command(
            "hours_import",
            "kirjastot",
            "--openings",
            "--single",
            kallio_kirkanta_id,
            "--date",
            date,
        )
        if change == "next_month":
            # When the month changes, the importer will by default import a new
            # set of dates. Period bounds should not change, but dates will be
            # partially new, old periods may disappear at the start and new periods may
            # appear at the end. Existing periods should survive the process unscathed
            # if new data holds no surprises and has the same weekly pattern. Past
            # periods should stay in the database, while current and future ones may
            # update.
            for index, day in enumerate(mock_data["data"]["schedules"]):
                # move the data forward exactly four weeks, so it starts in July
                # but with the same rotation
                mock_data["data"]["schedules"][index]["date"] = (
                    (datetime.fromisoformat(day["date"]) + timedelta(weeks=4))
                    .date()
                    .strftime("%Y-%m-%d")
                )
        if change == "edit":
            # Change Saturday opening in base period
            for index, day in enumerate(mock_data["data"]["schedules"]):
                weekday = datetime.fromisoformat(day["date"]).date().isoweekday()
                if weekday == 6 and day["period"] == int(base_period_id):
                    mock_data["data"]["schedules"][index]["times"] = [
                        {"to": "15:00", "from": "11:00", "status": 2}
                    ]
        if change == "remove":
            # Remove Saturday opening in base period
            for index, day in enumerate(mock_data["data"]["schedules"]):
                weekday = datetime.fromisoformat(day["date"]).date().isoweekday()
                if weekday == 6 and day["period"] == int(base_period_id):
                    mock_data["data"]["schedules"][index]["times"] = []
                    mock_data["data"]["schedules"][index]["closed"] = True
            # If exception period exists, remove it too
            try:
                midsummer_period_id = next(period_ids)
                mock_data["refs"]["period"].pop(midsummer_period_id)
                for index, day in enumerate(mock_data["data"]["schedules"]):
                    weekday = datetime.fromisoformat(day["date"]).date().isoweekday()
                    if day["period"] == int(midsummer_period_id):
                        day_to_change = mock_data["data"]["schedules"][index]
                        day_to_change["period"] = int(base_period_id)
                        if weekday in {4, 5}:
                            day_to_change["times"] = [
                                {"to": "10:00", "from": "08:00", "status": 2},
                                {"to": "20:00", "from": "10:00", "status": 1},
                            ]
                            day_to_change["closed"] = False
                        if weekday in {6, 7}:
                            day_to_change["times"] = []
                            day_to_change["closed"] = True
            except StopIteration:
                pass
        if change == "add":
            # Add Sunday opening in base period
            for index, day in enumerate(mock_data["data"]["schedules"]):
                if datetime.fromisoformat(day["date"]).date().isoweekday() == 7 and day[
                    "period"
                ] == int(base_period_id):
                    mock_data["data"]["schedules"][index]["times"] = [
                        {"to": "16:00", "from": "10:00", "status": 1}
                    ]
                    mock_data["data"]["schedules"][index]["closed"] = False
            # If exception period exists, add another exception
            try:
                midsummer_period_id = next(period_ids)
                new_id = int(midsummer_period_id) + 1
                mock_data["refs"]["period"][str(new_id)] = {
                    "id": new_id,
                    "library": 84860,
                    "validFrom": "2020-06-23",
                    "validUntil": "2020-06-23",
                    "isException": True,
                    "name": "Yllätyspäivä",
                    "description": "Suddenly, we are closed",
                }
                for index, day in enumerate(mock_data["data"]["schedules"]):
                    if day["date"] == "2020-06-23":
                        mock_data["data"]["schedules"][index]["period"] = new_id
                        mock_data["data"]["schedules"][index]["times"] = []
                        mock_data["data"]["schedules"][index]["closed"] = True
                        mock_data["data"]["schedules"][index]["info"] = "Yllätyspäivä"
            except StopIteration:
                pass

        # TODO: should we test for periods edited mid-period so that old dates may
        # hold old data, and only update periods based on current and future dates??
        if change:
            print("made a change")  # noqa: T201
            print(change)  # noqa: T201
        if change == "next_month":
            date = "2020-07-01"
            url_to_mock = (
                f"https://api.kirjastot.fi/v4/library/{kallio_kirkanta_id}/?with=schedules"
                "&refs=period&period.start=2020-07-01&period.end=2021-07-01"
            )

        # Calling the import twice checks idempotency, even if no change was made
        requests_mock.get(url_to_mock, text=json.dumps(mock_data))
        call_command(
            "hours_import",
            "kirjastot",
            "--openings",
            "--single",
            kallio_kirkanta_id,
            "--date",
            date,
        )

        # Finally, if we run the import for both June and July, we want the June
        # opening hours to stay true to the original file even after July data
        # was added. Rotation of four weeks should exactly match original data.
        if change == "next_month":
            date = "2020-06-01"
            url_to_mock = (
                f"https://api.kirjastot.fi/v4/library/{kallio_kirkanta_id}/?with=schedules"
                "&refs=period&period.start=2020-06-01&period.end=2021-06-01"
            )
            test_file_path = os.path.join(
                os.path.dirname(__file__), "fixtures", test_file_name
            )
            with open(test_file_path) as f:
                mock_data = json.load(f)
            requests_mock.get(url_to_mock, text=json.dumps(mock_data))
            # Don't import June data again, just do the check
            call_command(
                "hours_import",
                "kirjastot",
                "--check",
                "--single",
                kallio_kirkanta_id,
                "--date",
                date,
            )

    return {
        "testing_period_endless": endless,
        "made_a_change": change,
        "get_data": _mock_library_data,
    }


@pytest.fixture
def mock_hauki_data(mock_tprek_data, requests_mock, request):
    periods_file_name = "test_import_hauki_periods.json"
    periods_file_path = os.path.join(
        os.path.dirname(__file__), "fixtures", periods_file_name
    )
    with open(periods_file_path) as periods_file:
        periods = json.load(periods_file)
    requests_mock.get(
        "https://hauki-test.oc.hel.ninja/v1/date_period/?resource=1",
        text=json.dumps(periods),
    )
    call_command("hours_import", "hauki", openings=True)
    return {
        "periods": periods,
    }


tprek_parameters = []
for merge in [False, True]:
    for change in [None, "edit", "remove", "add"]:
        tprek_parameters.append({"merge": merge, "change": change})


@pytest.mark.django_db
@pytest.mark.parametrize("mock_tprek_data", tprek_parameters, indirect=True)
def test_import_tprek(mock_tprek_data):
    # The results should depend on whether we merge identical connections
    # and whether we have changed the connections and rerun the import
    merge = mock_tprek_data["merged_specific_connections"]
    change = mock_tprek_data["made_a_change_and_rerun"]

    # Check created objects
    if change == "add":
        expected_n_resources = 24
    elif change == "remove":
        expected_n_resources = 22
    else:
        expected_n_resources = 23
    if change == "edit":
        expected_n_merged_resources = 22
    else:
        expected_n_merged_resources = 21
    if not merge:
        assert Resource.objects.filter(is_public=True).count() == expected_n_resources
    else:
        assert (
            Resource.objects.filter(is_public=True).count()
            == expected_n_merged_resources
        )
    assert DataSource.objects.count() == 4
    assert Organization.objects.count() == 1
    external_origins = 5
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
    kallio = Resource.objects.get(origins__data_source="tprek", origins__origin_id=8215)
    oodi = Resource.objects.get(origins__data_source="tprek", origins__origin_id=51342)
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
    assert kallio.organization_id == f"tprek:{mock_kallio['dept_id']}"
    assert kallio.resource_type == ResourceType.UNIT
    assert (
        kallio.extra_data["citizen_url"]
        == f"https://palvelukartta.hel.fi/fi/unit/{mock_kallio['id']}"
    )
    origins = {x.data_source_id: x for x in kallio.origins.all()}
    assert "tprek" in origins
    assert origins["tprek"].origin_id == str(mock_kallio["id"])
    for source in mock_kallio["sources"]:
        if source["source"] == "internal":
            assert kallio.extra_data["admin_url"] == (
                "https://tpr.hel.fi/tprperhe/TPR/UI/ServicePoint"
                f"/ServicePointEdit/{source['id']}"
            )
        else:
            assert source["source"] in origins
            assert origins[source["source"]].origin_id == source["id"]

    # Check the right connections are under the right units
    subsections = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.SUBSECTION, is_public=True
    )
    contacts = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.CONTACT, is_public=True
    )
    online_services = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.ONLINE_SERVICE, is_public=True
    )
    entrances = Resource.objects.order_by("pk").filter(
        resource_type=ResourceType.ENTRANCE, is_public=True
    )

    # Check subsections
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
        if change == "edit":
            # reservations changed in kallio
            (
                reservationskallio,
                directorkallio,
                directoroodi,
                librarian,
                reservations,
            ) = contacts
        else:
            (reservations, directorkallio, directoroodi, librarian) = contacts
        if change == "remove":
            # reservations removed in kallio
            contacts_expected_in_kallio = {directorkallio, librarian}
        elif change == "edit":
            # reservations changed in kallio
            contacts_expected_in_kallio = {
                directorkallio,
                reservationskallio,
                librarian,
            }
        else:
            contacts_expected_in_kallio = {reservations, directorkallio, librarian}
        contacts_expected_in_oodi = {reservations, directoroodi, librarian}
    else:
        if change == "remove":
            # reservations removed in kallio
            (
                reservationsoodi,
                directorkallio,
                directoroodi,
                librariankallio,
                librarianoodi,
            ) = contacts
            contacts_expected_in_kallio = {directorkallio, librariankallio}
        else:
            (
                reservationskallio,
                reservationsoodi,
                directorkallio,
                directoroodi,
                librariankallio,
                librarianoodi,
            ) = contacts
            contacts_expected_in_kallio = {
                reservationskallio,
                directorkallio,
                librariankallio,
            }
        contacts_expected_in_oodi = {reservationsoodi, directoroodi, librarianoodi}

    assert contacts_expected_in_kallio == set(
        kallio.children.filter(resource_type=ResourceType.CONTACT, is_public=True)
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

    # Check that the fields in subsections are imported correctly
    mock_subsection = next(
        filter(
            lambda x: x["connection_id"] == "contact-5", mock_tprek_data["connections"]
        )
    )
    mock_contact = next(
        filter(
            lambda x: x["connection_id"] == "contact-28", mock_tprek_data["connections"]
        )
    )
    mock_online_service = next(
        filter(
            lambda x: x["connection_id"] == "contact-21", mock_tprek_data["connections"]
        )
    )
    mock_entrance = next(
        filter(
            lambda x: x["connection_id"] == "contact-14", mock_tprek_data["connections"]
        )
    )
    assert covid1.name_fi == mock_subsection["name_fi"]
    assert covid1.description_fi == mock_subsection["www_fi"]
    librarian = librarian if merge else librariankallio
    assert librarian.name_fi == mock_contact["name_fi"][:-12]
    assert (
        librarian.description_fi
        == f"{mock_contact['contact_person']} {mock_contact['email']} {mock_contact['phone']}"  # noqa
    )
    assert hydrobic.name_fi == mock_online_service["name_fi"]
    assert hydrobic.description_fi == mock_online_service["www_fi"]
    assert mikkolankuja.name_fi == mock_entrance["name_fi"]


kirjastot_parameters = []
for endless in [False, True]:
    for change in [None, "next_month", "edit", "remove", "add"]:
        kirjastot_parameters.append({"endless": endless, "change": change})


@pytest.mark.django_db
@pytest.mark.parametrize("mock_library_data", kirjastot_parameters, indirect=True)
def test_import_kirjastot_simple(mock_library_data):
    # The results should depend on possible changes in data between import runs
    change = mock_library_data["made_a_change"]

    test_file_name = "test_import_kirjastot_data_simple.json"
    mock_library_data["get_data"](test_file_name)

    # Check created objects
    assert DatePeriod.objects.count() == 1
    expected_n_time_spans = 4 if change == "remove" or change == "add" else 5
    assert TimeSpan.objects.count() == expected_n_time_spans
    assert TimeSpanGroup.objects.count() == 1
    # Simple data should have pattern repeating weekly
    assert Rule.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("mock_library_data", kirjastot_parameters, indirect=True)
def test_import_kirjastot_pattern(mock_library_data):
    # The results should depend on possible changes in data between import runs
    change = mock_library_data["made_a_change"]

    test_file_name = "test_import_kirjastot_data_pattern.json"
    mock_library_data["get_data"](test_file_name)

    # Check created objects
    if change == "next_month":
        expected_n_periods = 9
    elif change == "remove":
        expected_n_periods = 1
    elif change == "add":
        expected_n_periods = 6
    else:
        expected_n_periods = 5
    assert DatePeriod.objects.count() == expected_n_periods

    if change == "next_month":
        expected_n_timespan_groups = 5
    elif change == "remove":
        expected_n_timespan_groups = 3
        timespan_groups_of_removed_periods = 1
        expected_n_timespan_groups += timespan_groups_of_removed_periods
    else:
        expected_n_timespan_groups = 4
    assert TimeSpanGroup.objects.count() == expected_n_timespan_groups
    assert Rule.objects.count() == 2
    periods_by_start = DatePeriod.objects.order_by("start_date")

    # Data has overlapping periods
    if change == "next_month":
        # we imported first June, then July, and both months had a copy of
        # exception period. Summer period should stay the same
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
            midsummer_pre_eve_copy,
            midsummer_eve_copy,
            midsummer_sat_copy,
            midsummer_sun_copy,
        ) = periods_by_start
        assert midsummer_pre_eve_copy.time_span_groups.count() == 1
        assert midsummer_eve_copy.time_span_groups.count() == 0
        assert midsummer_sat_copy.time_span_groups.count() == 0
        assert midsummer_sun_copy.time_span_groups.count() == 0
    elif change == "remove":
        (summer_period,) = periods_by_start
    elif change == "add":
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
            extra_exception,
        ) = periods_by_start
        assert midsummer_pre_eve.time_span_groups.count() == 1
        assert midsummer_eve.time_span_groups.count() == 0
        assert midsummer_sat.time_span_groups.count() == 0
        assert midsummer_sun.time_span_groups.count() == 0
        assert extra_exception.time_span_groups.count() == 0
    else:
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
        ) = periods_by_start
        assert midsummer_pre_eve.time_span_groups.count() == 1
        assert midsummer_eve.time_span_groups.count() == 0
        assert midsummer_sat.time_span_groups.count() == 0
        assert midsummer_sun.time_span_groups.count() == 0
    assert summer_period.time_span_groups.count() == 3

    # Data should have pattern repeating biweekly even with
    # missing days at start, end and middle
    (weekends, first_week, second_week) = summer_period.time_span_groups.all()
    assert weekends.rules.count() == 0
    assert first_week.rules.all()[0].start == 1
    assert first_week.rules.all()[0].frequency_ordinal == 2
    assert second_week.rules.all()[0].start == 2
    assert second_week.rules.all()[0].frequency_ordinal == 2


@pytest.mark.django_db
@pytest.mark.parametrize("mock_library_data", kirjastot_parameters, indirect=True)
def test_import_kirjastot_complex(mock_library_data):
    # The results should depend on possible changes in data between import runs
    change = mock_library_data["made_a_change"]

    test_file_name = "test_import_kirjastot_data_complex.json"
    mock_library_data["get_data"](test_file_name)

    # Check created objects
    if change == "next_month":
        expected_n_periods = 9
    elif change == "remove":
        expected_n_periods = 1
    elif change == "add":
        expected_n_periods = 6
    else:
        expected_n_periods = 5
    assert DatePeriod.objects.count() == expected_n_periods

    if change == "next_month":
        expected_n_timespan_groups = 9
    elif change == "remove":
        expected_n_timespan_groups = 7
        timespan_groups_of_removed_periods = 1
        expected_n_timespan_groups += timespan_groups_of_removed_periods
    else:
        expected_n_timespan_groups = 8
    assert TimeSpanGroup.objects.count() == expected_n_timespan_groups
    assert Rule.objects.count() == 6
    periods_by_start = DatePeriod.objects.order_by("start_date")

    # Complex data has overlapping periods
    if change == "next_month":
        # we imported first June, then July, and both months had a copy of
        # exception period. Summer period should stay the same
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
            midsummer_pre_eve_copy,
            midsummer_eve_copy,
            midsummer_sat_copy,
            midsummer_sun_copy,
        ) = periods_by_start
        assert midsummer_pre_eve_copy.time_span_groups.count() == 1
        assert midsummer_eve_copy.time_span_groups.count() == 0
        assert midsummer_sat_copy.time_span_groups.count() == 0
        assert midsummer_sun_copy.time_span_groups.count() == 0
    elif change == "remove":
        (summer_period,) = periods_by_start
    elif change == "add":
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
            extra_exception,
        ) = periods_by_start
        assert midsummer_pre_eve.time_span_groups.count() == 1
        assert midsummer_eve.time_span_groups.count() == 0
        assert midsummer_sat.time_span_groups.count() == 0
        assert midsummer_sun.time_span_groups.count() == 0
        assert extra_exception.time_span_groups.count() == 0
    else:
        (
            summer_period,
            midsummer_pre_eve,
            midsummer_eve,
            midsummer_sat,
            midsummer_sun,
        ) = periods_by_start
        assert midsummer_pre_eve.time_span_groups.count() == 1
        assert midsummer_eve.time_span_groups.count() == 0
        assert midsummer_sat.time_span_groups.count() == 0
        assert midsummer_sun.time_span_groups.count() == 0
    assert summer_period.time_span_groups.count() == 7

    # Complex data has different rules for different weekdays
    (
        weekends,
        first_week_thu,
        second_week_thu,
        first_week,
        second_week,
        third_week,
        fourth_week,
    ) = summer_period.time_span_groups.all()
    assert weekends.rules.count() == 0
    assert first_week.rules.all()[0].start == 1
    assert first_week.rules.all()[0].frequency_ordinal == 4
    assert second_week.rules.all()[0].start == 2
    assert second_week.rules.all()[0].frequency_ordinal == 4
    assert third_week.rules.all()[0].start == 3
    assert third_week.rules.all()[0].frequency_ordinal == 4
    assert fourth_week.rules.all()[0].start == 4
    assert fourth_week.rules.all()[0].frequency_ordinal == 4
    assert first_week_thu.rules.all()[0].start == 1
    assert first_week_thu.rules.all()[0].frequency_ordinal == 2
    assert second_week_thu.rules.all()[0].start == 2
    assert second_week_thu.rules.all()[0].frequency_ordinal == 2


KALLIO_KIRKANTA_ID = 84860
KIRJASTOT_URL = (
    f"https://api.kirjastot.fi/v4/library/{KALLIO_KIRKANTA_ID}/?with=schedules"
    "&refs=period&period.start=2020-06-01&period.end=2021-06-01"
)
SUMMER_PERIOD_ID = "343802"
SUMMER_PERIOD_TEXT = "Kesä2020"
MIDSUMMER_PERIOD_ID = "339753"


def translate_kirjastot_data(data: dict, lang: str) -> dict:
    """
    Returns a copy of the kirjastot.fi API data with its texts in the given language,
    like the API returns them with the lang parameter.
    """
    data = copy.deepcopy(data)
    for period in data["refs"]["period"].values():
        period["name"] = f"{period['name']} ({lang})"
        period["description"] = f"{period['description']} ({lang})"
    for schedule in data["data"]["schedules"]:
        if schedule["info"]:
            schedule["info"] = f"{schedule['info']} ({lang})"
    return data


def mock_kirjastot_data_by_language(requests_mock, data_by_language: dict):
    for lang, data in data_by_language.items():
        requests_mock.get(f"{KIRJASTOT_URL}&lang={lang}", text=json.dumps(data))


def import_kirjastot(*args):
    call_command(
        "hours_import",
        "kirjastot",
        "--openings",
        "--single",
        KALLIO_KIRKANTA_ID,
        "--date",
        "2020-06-01",
        *args,
    )


def get_requested_languages(requests_mock, start: int = 0) -> list:
    return [r.qs.get("lang") for r in requests_mock.request_history[start:]]


def get_names(obj) -> tuple:
    return obj.name_fi, obj.name_sv, obj.name_en


def get_descriptions(obj) -> tuple:
    return obj.description_fi, obj.description_sv, obj.description_en


def get_history_counts() -> tuple:
    return (
        DatePeriod.history.count(),
        TimeSpan.history.count(),
        Rule.history.count(),
    )


def change_summer_period_texts(data_by_language: dict, field: str):
    for lang, data in data_by_language.items():
        data["refs"]["period"][SUMMER_PERIOD_ID][field] = f"Changed {lang}"


@pytest.fixture
def mock_multilingual_library_data(requests_mock):
    """
    Creates a library and mocks its kirjastot.fi API data in fi, sv and en. Returns
    the mocked data by language, so that it can be changed and mocked again.
    """
    kirkanta = DataSource.objects.create(id="kirkanta")
    kallio = Resource.objects.create()
    ResourceOrigin.objects.create(
        data_source=kirkanta, origin_id=KALLIO_KIRKANTA_ID, resource=kallio
    )
    test_file_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "test_import_kirjastot_data_pattern.json"
    )
    with open(test_file_path) as f:
        data = json.load(f)
    for schedule in data["data"]["schedules"]:
        if schedule["date"] == "2020-06-20":
            # Without the info, the name of the holiday is used
            schedule["info"] = None

    data_by_language = {
        "fi": data,
        "sv": translate_kirjastot_data(data, "sv"),
        "en": translate_kirjastot_data(data, "en"),
    }
    mock_kirjastot_data_by_language(requests_mock, data_by_language)
    return data_by_language


@pytest.mark.django_db
def test_import_kirjastot_languages(mock_multilingual_library_data, requests_mock):
    import_kirjastot()

    # The data is fetched once in each language, the default language first
    assert get_requested_languages(requests_mock) == [["fi"], ["sv"], ["en"]]
    assert DatePeriod.objects.count() == 5
    summer_period = DatePeriod.objects.get(origins__origin_id=SUMMER_PERIOD_ID)
    summer_texts = (
        SUMMER_PERIOD_TEXT,
        f"{SUMMER_PERIOD_TEXT} (sv)",
        f"{SUMMER_PERIOD_TEXT} (en)",
    )
    assert get_names(summer_period) == summer_texts
    assert get_descriptions(summer_period) == summer_texts
    pre_eve = DatePeriod.objects.get(
        origins__origin_id=f"{MIDSUMMER_PERIOD_ID}-2020-06-18"
    )
    pre_eve_names = (
        "Juhannuksen aaton aatto",
        "Juhannuksen aaton aatto (sv)",
        "Juhannuksen aaton aatto (en)",
    )
    assert get_names(pre_eve) == pre_eve_names
    assert get_descriptions(pre_eve) == ("Juhannus", "Juhannus (sv)", "Juhannus (en)")
    pre_eve_time_spans = TimeSpan.objects.filter(group__period=pre_eve)
    assert pre_eve_time_spans.count() == 2
    for time_span in pre_eve_time_spans:
        assert get_names(time_span) == pre_eve_names
    midsummer_day = DatePeriod.objects.get(
        origins__origin_id=f"{MIDSUMMER_PERIOD_ID}-2020-06-20"
    )
    assert get_names(midsummer_day) == (
        "Juhannuspäivä",
        "Midsommardagen",
        "Midsummer Day",
    )

    # Importing the same data again changes nothing
    history_counts = get_history_counts()
    import_kirjastot()
    assert get_history_counts() == history_counts


@pytest.mark.django_db
def test_import_kirjastot_single_language(
    mock_multilingual_library_data, requests_mock
):
    import_kirjastot()
    change_summer_period_texts(mock_multilingual_library_data, "name")
    mock_kirjastot_data_by_language(requests_mock, mock_multilingual_library_data)
    n_requests = len(requests_mock.request_history)

    import_kirjastot("--language", "sv")

    # The data in fi is fetched for the opening hours, but only the texts in sv
    # are updated
    assert get_requested_languages(requests_mock, n_requests) == [["fi"], ["sv"]]
    assert DatePeriod.objects.count() == 5
    summer_period = DatePeriod.objects.get(origins__origin_id=SUMMER_PERIOD_ID)
    assert get_names(summer_period) == (
        SUMMER_PERIOD_TEXT,
        "Changed sv",
        f"{SUMMER_PERIOD_TEXT} (en)",
    )


@pytest.mark.django_db
def test_import_kirjastot_single_language_failed_fetch_keeps_data(
    mock_multilingual_library_data, requests_mock
):
    import_kirjastot()
    change_summer_period_texts(mock_multilingual_library_data, "name")
    mock_kirjastot_data_by_language(requests_mock, mock_multilingual_library_data)
    requests_mock.get(f"{KIRJASTOT_URL}&lang=sv", status_code=500)
    history_counts = get_history_counts()

    import_kirjastot("--language", "sv")

    # The opening hours come from the data in fi, so no periods are removed, and
    # no texts are updated without the data in sv
    assert DatePeriod.objects.count() == 5
    summer_period = DatePeriod.objects.get(origins__origin_id=SUMMER_PERIOD_ID)
    assert get_names(summer_period) == (
        SUMMER_PERIOD_TEXT,
        f"{SUMMER_PERIOD_TEXT} (sv)",
        f"{SUMMER_PERIOD_TEXT} (en)",
    )
    assert get_history_counts() == history_counts


@pytest.mark.django_db
def test_import_kirjastot_failed_language_keeps_texts(
    mock_multilingual_library_data, requests_mock
):
    import_kirjastot()
    change_summer_period_texts(mock_multilingual_library_data, "name")
    mock_kirjastot_data_by_language(requests_mock, mock_multilingual_library_data)
    requests_mock.get(f"{KIRJASTOT_URL}&lang=sv", status_code=500)

    import_kirjastot()

    # No periods are removed, and the existing texts in sv are kept
    assert DatePeriod.objects.count() == 5
    summer_period = DatePeriod.objects.get(origins__origin_id=SUMMER_PERIOD_ID)
    assert get_names(summer_period) == (
        "Changed fi",
        f"{SUMMER_PERIOD_TEXT} (sv)",
        "Changed en",
    )
    midsummer_day = DatePeriod.objects.get(
        origins__origin_id=f"{MIDSUMMER_PERIOD_ID}-2020-06-20"
    )
    assert get_names(midsummer_day) == (
        "Juhannuspäivä",
        "Midsommardagen",
        "Midsummer Day",
    )


@pytest.mark.django_db
def test_import_kirjastot_keeps_existing_descriptions(
    mock_multilingual_library_data, requests_mock
):
    import_kirjastot()
    summer_period = DatePeriod.objects.get(origins__origin_id=SUMMER_PERIOD_ID)
    # The description is edited in Hauki in fi, and removed in sv
    summer_period.description_fi = "Muokattu Haukissa"
    summer_period.description_sv = ""
    summer_period.save()
    change_summer_period_texts(mock_multilingual_library_data, "description")
    mock_kirjastot_data_by_language(requests_mock, mock_multilingual_library_data)

    import_kirjastot()

    summer_period.refresh_from_db()
    # Existing descriptions are never overwritten, only the empty ones are filled
    assert get_descriptions(summer_period) == (
        "Muokattu Haukissa",
        "Changed sv",
        f"{SUMMER_PERIOD_TEXT} (en)",
    )


@pytest.mark.django_db
def test_import_kirjastot_check_fetches_only_default_language(
    mock_multilingual_library_data, requests_mock
):
    import_kirjastot()
    n_requests = len(requests_mock.request_history)

    call_command(
        "hours_import",
        "kirjastot",
        "--check",
        "--single",
        KALLIO_KIRKANTA_ID,
        "--date",
        "2020-06-01",
    )

    # The texts are not needed for checking the opening hours
    assert get_requested_languages(requests_mock, n_requests) == [["fi"]]


@pytest.mark.django_db
def test_import_language_option_not_supported():
    with pytest.raises(CommandError, match="does not support the --language option"):
        call_command("hours_import", "tprek", "--resources", "--language", "sv")


@pytest.mark.django_db
def test_import_language_option_invalid_language():
    with pytest.raises(CommandError, match="invalid choice"):
        call_command("hours_import", "kirjastot", "--openings", "--language", "de")


@pytest.mark.django_db
def test_import_hauki(mock_hauki_data):
    kallio_tprek_id = 8215
    kallio = Resource.objects.get(
        origins__data_source="tprek", origins__origin_id=kallio_tprek_id
    )
    # Check created objects
    assert DatePeriod.objects.filter(resource=kallio).count() == 1
    assert kallio.date_periods.count() == 1
    expected_n_time_spans = 5
    assert (
        TimeSpan.objects.filter(group__period__resource=kallio).count()
        == expected_n_time_spans
    )
    assert TimeSpanGroup.objects.filter(period__resource=kallio).count() == 1
    # Simple data should have pattern repeating weekly
    assert Rule.objects.count() == 0
