from datetime import date, time

import pytest

from hours.enums import State, Weekday
from hours.importer.kirjastot import KirjastotImporter, KirjastotImporterError
from hours.models import DatePeriod, ResourceOrigin, TimeSpan
from hours.tests.conftest import ResourceFactory

KIRKANTA_ID = "84860"
KIRKANTA_URL = f"https://api.kirjastot.fi/v4/library/{KIRKANTA_ID}/"
START_DATE = date(2020, 6, 1)
END_DATE = date(2021, 6, 1)


def create_library(importer: KirjastotImporter):
    library = ResourceFactory()
    ResourceOrigin.objects.create(
        data_source=importer.data_source, origin_id=KIRKANTA_ID, resource=library
    )
    return library


def get_names(obj) -> tuple:
    return obj.name_fi, obj.name_sv, obj.name_en


def get_descriptions(obj) -> tuple:
    return obj.description_fi, obj.description_sv, obj.description_en


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


def test_get_languages_default():
    # The default language first, since its data is used for the opening hours
    assert KirjastotImporter.get_languages() == ["fi", "sv", "en"]


def test_get_languages_single_language():
    # The default language is always fetched for the opening hours
    assert KirjastotImporter.get_languages("sv") == ["fi", "sv"]
    assert KirjastotImporter.get_languages("fi") == ["fi"]


def test_get_languages_unsupported_language():
    with pytest.raises(KirjastotImporterError, match="Unsupported language de"):
        KirjastotImporter.get_languages("de")


@pytest.mark.django_db
def test_importer_languages_from_options():
    importer = KirjastotImporter({})

    assert importer.language is None
    assert importer.languages == ["fi", "sv", "en"]

    importer = KirjastotImporter({"language": "sv"})

    assert importer.language == "sv"
    assert importer.languages == ["fi", "sv"]
    assert importer.primary_language == "fi"


@pytest.mark.django_db
def test_get_hours_from_api_lang_param(requests_mock):
    importer = KirjastotImporter({})
    library = create_library(importer)
    requests_mock.get(KIRKANTA_URL, json={"total": 1})

    importer.get_hours_from_api(library, START_DATE, END_DATE, lang="sv")
    assert requests_mock.last_request.qs["lang"] == ["sv"]

    importer.get_hours_from_api(library, START_DATE, END_DATE)
    assert "lang" not in requests_mock.last_request.qs


@pytest.mark.django_db
def test_get_hours_for_languages_skips_failed_language(requests_mock):
    importer = KirjastotImporter({})
    library = create_library(importer)
    for lang in ("fi", "en"):
        requests_mock.get(f"{KIRKANTA_URL}?lang={lang}", json={"total": 1, "l": lang})
    requests_mock.get(f"{KIRKANTA_URL}?lang=sv", status_code=500)

    data_by_language = importer.get_hours_for_languages(library, START_DATE, END_DATE)

    # The language that could not be fetched is left out, so its texts are kept
    assert list(data_by_language) == ["fi", "en"]
    assert data_by_language["en"]["l"] == "en"
    requested_languages = [r.qs["lang"] for r in requests_mock.request_history]
    assert requested_languages == [["fi"], ["sv"], ["en"]]


@pytest.mark.django_db
def test_get_hours_for_languages_primary_language_fails(requests_mock):
    importer = KirjastotImporter({})
    library = create_library(importer)
    requests_mock.get(KIRKANTA_URL, status_code=500)

    assert importer.get_hours_for_languages(library, START_DATE, END_DATE) == {}
    # The texts are not fetched without the opening hours
    assert requests_mock.call_count == 1


def test_annotate_translations():
    def get_data(lang):
        return {
            "refs": {
                "period": {
                    "1": {
                        "id": 1,
                        "name": f"Period {lang}",
                        "description": f"Description {lang}",
                    }
                }
            },
            "data": {
                "schedules": [
                    {"date": "2020-06-19", "period": 1, "info": f"Info {lang}"},
                    {"date": "2020-06-20", "period": 1, "info": None},
                ]
            },
        }

    data_by_language = {lang: get_data(lang) for lang in ("fi", "sv", "en")}
    # The period and the first schedule are missing from the data in en
    data_by_language["en"]["refs"]["period"] = {}
    data_by_language["en"]["data"]["schedules"].pop(0)
    data = data_by_language["fi"]

    KirjastotImporter.annotate_translations(data, data_by_language)

    period = data["refs"]["period"]["1"]
    assert period["name_translations"] == {
        "fi": "Period fi",
        "sv": "Period sv",
        "en": None,
    }
    assert period["description_translations"] == {
        "fi": "Description fi",
        "sv": "Description sv",
        "en": None,
    }
    first_day, second_day = data["data"]["schedules"]
    assert first_day["info_translations"] == {
        "fi": "Info fi",
        "sv": "Info sv",
        "en": None,
    }
    assert second_day["info_translations"] == {"fi": None, "sv": None, "en": None}


def test_annotate_translations_without_data():
    data = {}

    KirjastotImporter.annotate_translations(data, {})

    assert data == {}


def get_midsummer_period() -> dict:
    return {
        "id": 1,
        "validFrom": "2020-06-19",
        "validUntil": "2020-06-20",
        "name_translations": {"fi": "Juhannus", "sv": "Midsommar", "en": "Midsummer"},
        "description_translations": {"fi": "Kuvaus", "sv": "", "en": None},
        "days": [
            {
                "date": date(2020, 6, 19),
                "closed": False,
                "times": [{"from": "10:00", "to": "14:00", "status": 1}],
                "info_translations": {"fi": "Aatto", "sv": "Afton", "en": "Eve"},
            },
            {
                "date": date(2020, 6, 20),
                "closed": True,
                "times": [],
                # Without the info, the name of the holiday is used
                "info_translations": {"fi": None, "sv": "", "en": None},
            },
        ],
    }


@pytest.mark.django_db
def test_separate_exceptional_periods_translations():
    importer = KirjastotImporter({})
    library = ResourceFactory()

    eve, midsummer_day = importer.separate_exceptional_periods(
        library, get_midsummer_period()
    )

    assert eve["name"] == {"fi": "Aatto", "sv": "Afton", "en": "Eve"}
    # Empty descriptions are stored as None
    assert eve["description"] == {"fi": "Kuvaus", "sv": None, "en": None}
    (time_span,) = eve["time_span_groups"][0]["time_spans"]
    assert time_span["name"] == {"fi": "Aatto", "sv": "Afton", "en": "Eve"}
    assert midsummer_day["name"] == {
        "fi": "Juhannuspäivä",
        "sv": "Midsommardagen",
        "en": "Midsummer Day",
    }
    assert midsummer_day["description"] == {"fi": "Kuvaus", "sv": None, "en": None}


@pytest.mark.django_db
def test_separate_exceptional_periods_closed_period_translations():
    importer = KirjastotImporter({})
    library = ResourceFactory()
    period = get_midsummer_period()
    period["days"] = period["days"][1:]

    (closed_period,) = importer.separate_exceptional_periods(library, period)

    assert closed_period["name"] == {
        "fi": "Juhannus",
        "sv": "Midsommar",
        "en": "Midsummer",
    }
    assert closed_period["description"] == {"fi": "Kuvaus", "sv": None, "en": None}
    assert closed_period["resource_state"] == State.CLOSED


@pytest.mark.django_db
def test_separate_exceptional_periods_without_translations():
    importer = KirjastotImporter({})
    library = ResourceFactory()
    period = {
        "id": 1,
        "name": "Juhannus",
        "days": [
            {
                "date": date(2020, 6, 20),
                "closed": False,
                "times": [{"from": "10:00", "to": "14:00", "status": 1}],
                "info": None,
            },
        ],
    }

    (sub_period,) = importer.separate_exceptional_periods(library, period)

    # Without the annotated translations, the texts are in the primary language
    assert sub_period["name"] == {"fi": "Juhannuspäivä"}
    assert sub_period["description"] == {"fi": None}


@pytest.mark.django_db
def test_get_period_names_truncated():
    importer = KirjastotImporter({})
    period = {"name_translations": {"fi": "x" * 300, "sv": None, "en": ""}}

    assert importer._get_period_names(period) == {"fi": "x" * 255, "sv": None, "en": ""}


@pytest.mark.django_db
def test_update_fields_only_given_languages():
    importer = KirjastotImporter({})
    period = DatePeriod(name_fi="Nimi", name_sv="Namn", name_en="Name")

    importer._update_fields(
        period, {"name": {"fi": "Uusi", "sv": "Ny", "en": "New"}}, languages=["sv"]
    )

    assert get_names(period) == ("Nimi", "Ny", "Name")


@pytest.mark.django_db
def test_update_fields_only_fill_empty():
    importer = KirjastotImporter({})
    period = DatePeriod(
        description_fi="Olemassa oleva", description_sv=None, description_en=""
    )

    importer._update_fields(
        period,
        {"description": {"fi": "Uusi", "sv": "Ny", "en": "New"}},
        only_fill_empty=("description",),
    )

    assert get_descriptions(period) == ("Olemassa oleva", "Ny", "New")


@pytest.mark.django_db
def test_update_fields_only_fill_empty_keeps_empty_values():
    importer = KirjastotImporter({})
    period = DatePeriod(description_fi="", description_sv=None, description_en=None)
    period._changed = False

    importer._update_fields(
        period,
        {"description": {"fi": None, "sv": "", "en": None}},
        only_fill_empty=("description",),
    )

    # Empty values are not replaced with other empty values
    assert period._changed is False
    assert get_descriptions(period) == ("", None, None)


def get_translated_period_data(
    importer: KirjastotImporter, library, names: dict, time_span_names: dict
) -> dict:
    return {
        "origins": [{"origin_id": 13, "data_source_id": importer.data_source.id}],
        "resource": library,
        "name": names,
        "time_span_groups": [
            {
                "rules": [],
                "time_spans": [
                    {
                        "group": None,
                        "name": time_span_names,
                        "start_time": time(hour=10, minute=0),
                        "end_time": time(hour=18, minute=0),
                        "weekdays": [Weekday.MONDAY],
                        "resource_state": State.OPEN,
                        "full_day": False,
                    },
                ],
            }
        ],
    }


@pytest.mark.django_db
def test_save_dateperiod_translations():
    importer = KirjastotImporter({})
    library = ResourceFactory()

    period = importer.save_dateperiod(
        get_translated_period_data(
            importer,
            library,
            {"fi": "Kesä", "sv": "Sommar", "en": "Summer"},
            {"fi": "Aamu", "sv": "Morgon", "en": "Morning"},
        )
    )

    period.refresh_from_db()
    assert get_names(period) == ("Kesä", "Sommar", "Summer")
    time_span = TimeSpan.objects.get(group__period=period)
    assert get_names(time_span) == ("Aamu", "Morgon", "Morning")


@pytest.mark.django_db
def test_save_dateperiod_updates_only_given_languages():
    importer = KirjastotImporter({})
    library = ResourceFactory()
    importer.save_dateperiod(
        get_translated_period_data(
            importer,
            library,
            {"fi": "Kesä", "sv": "Sommar", "en": "Summer"},
            {"fi": "Aamu", "sv": "Morgon", "en": "Morning"},
        )
    )

    period = importer.save_dateperiod(
        get_translated_period_data(
            importer, library, {"sv": "Sommaren"}, {"sv": "Förmiddag"}
        ),
        languages=["sv"],
    )

    period.refresh_from_db()
    assert get_names(period) == ("Kesä", "Sommaren", "Summer")
    time_span = TimeSpan.objects.get(group__period=period)
    assert get_names(time_span) == ("Aamu", "Förmiddag", "Morning")


@pytest.mark.django_db
def test_save_dateperiod_new_objects_use_new_object_languages():
    importer = KirjastotImporter({})
    library = ResourceFactory()

    period = importer.save_dateperiod(
        get_translated_period_data(
            importer,
            library,
            {"fi": "Kesä", "sv": "Sommar"},
            {"fi": "Aamu", "sv": "Morgon"},
        ),
        languages=["sv"],
        new_object_languages=["fi", "sv"],
    )

    period.refresh_from_db()
    assert get_names(period) == ("Kesä", "Sommar", None)
    time_span = TimeSpan.objects.get(group__period=period)
    assert get_names(time_span) == ("Aamu", "Morgon", None)

    # Existing objects are only updated in the given languages
    period = importer.save_dateperiod(
        get_translated_period_data(
            importer,
            library,
            {"fi": "Kesäaika", "sv": "Sommaren"},
            {"fi": "Aamupäivä", "sv": "Förmiddag"},
        ),
        languages=["sv"],
        new_object_languages=["fi", "sv"],
    )

    period.refresh_from_db()
    assert get_names(period) == ("Kesä", "Sommaren", None)
    time_span = TimeSpan.objects.get(group__period=period)
    assert get_names(time_span) == ("Aamu", "Förmiddag", None)
