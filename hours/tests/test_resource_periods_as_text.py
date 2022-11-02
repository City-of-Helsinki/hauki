import datetime
import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import translation

from hours.enums import FrequencyModifier, RuleContext, RuleSubject, State, Weekday
from hours.models import Rule
from hours.serializers import DatePeriodSerializer
from hours.tests.conftest import (
    DatePeriodFactory,
    RuleFactory,
    TimeSpanFactory,
    TimeSpanGroupFactory,
)


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_resource_opening_hours_as_text_no_date_periods(resource, lang):
    with translation.override(lang):
        assert resource.get_date_periods_as_text() == ""


@pytest.mark.django_db
def test_resource_opening_hours_as_text(resource):
    DatePeriodFactory(
        name="Special hours",
        resource=resource,
        resource_state=State.CLOSED,
        start_date=datetime.date(year=2021, month=12, day=27),
        end_date=datetime.date(year=2022, month=1, day=2),
        override=True,
    )

    date_period = DatePeriodFactory(
        name="Regular opening hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span",
        group=time_span_group,
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=17, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.THURSDAY],
    )
    TimeSpanFactory(
        name="Test time span...",
        group=time_span_group,
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=19, minute=0),
        weekdays=[Weekday.FRIDAY, Weekday.SATURDAY],
    )

    TimeSpanFactory(
        name="Test time span 2",
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        weekdays=[Weekday.SUNDAY],
    )

    RuleFactory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.EVEN,
    )

    time_span_group2 = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span 3",
        group=time_span_group2,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
    )

    TimeSpanFactory(
        name="Test time span 4",
        group=time_span_group2,
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=13, minute=0),
        weekdays=Weekday.weekend(),
    )

    RuleFactory(
        group=time_span_group2,
        context=RuleContext.PERIOD,
        subject=RuleSubject.MONTH,
        frequency_ordinal=2,
    )

    RuleFactory(
        group=time_span_group2,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_modifier=FrequencyModifier.ODD,
    )

    with translation.override("en"):
        assert resource.get_date_periods_as_text() == (
            "\n"
            "========================================\n"
            "Regular opening hours\n"
            "Date period: Jan. 1, 2021 - Dec. 31, 2022\n"
            "Opening hours:\n"
            "\n"
            " Monday-Tuesday, Thursday 9 a.m.-5 p.m. Open\n"
            " Friday-Saturday 9 a.m.-7 p.m. Open\n"
            " Sunday 10 a.m.-2 p.m. Open\n"
            "\n"
            " In effect when every one of these match:\n"
            " - On even weeks in the period\n"
            "\n"
            " ---------------------------------------\n"
            "\n"
            " Monday-Tuesday 8 a.m.-4 p.m. Open\n"
            " Saturday-Sunday 9 a.m.-1 p.m. Open\n"
            "\n"
            " In effect when every one of these match:\n"
            " - Every 2nd month in the period\n"
            " - On odd weeks in the period\n"
            "\n"
            "========================================\n"
            "Special hours\n"
            "Date period: Dec. 27, 2021 - Jan. 2, 2022\n"
            "Opening hours:\n"
            "\n"
            " Closed\n"
            "\n"
            "========================================\n"
        )

    with translation.override("fi"):
        assert resource.get_date_periods_as_text() == (
            "\n"
            "========================================\n"
            "Regular opening hours\n"
            "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
            "Aukioloajat:\n"
            "\n"
            " Maanantai-Tiistai, Torstai 9.00-17.00 Auki\n"
            " Perjantai-Lauantai 9.00-19.00 Auki\n"
            " Sunnuntai 10.00-14.00 Auki\n"
            "\n"
            " Voimassa kun kaikki seuraavat pätevät:\n"
            " - Jakson jokainen parillinen viikko\n"
            "\n"
            " ---------------------------------------\n"
            "\n"
            " Maanantai-Tiistai 8.00-16.00 Auki\n"
            " Lauantai-Sunnuntai 9.00-13.00 Auki\n"
            "\n"
            " Voimassa kun kaikki seuraavat pätevät:\n"
            " - Jakson joka 2. kuukausi\n"
            " - Jakson jokainen pariton viikko\n"
            "\n"
            "========================================\n"
            "Special hours\n"
            "Aikajakso: 27. joulukuuta 2021 - 2. tammikuuta 2022\n"
            "Aukioloajat:\n"
            "\n"
            " Suljettu\n"
            "\n"
            "========================================\n"
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "modifier", [None, FrequencyModifier.EVEN, FrequencyModifier.ODD]
)
@pytest.mark.parametrize("start", [None, 1, 2, -1, -2])
@pytest.mark.parametrize("ordinal", [None, 1, 4])
@pytest.mark.parametrize("subject", list(RuleSubject))
@pytest.mark.parametrize("context", list(RuleContext))
def test_rule_as_text_frequency_ordinal(context, subject, start, ordinal, modifier):
    if not any([start, ordinal, modifier]) or (
        subject == RuleSubject.MONTH and context == RuleContext.MONTH
    ):
        pytest.skip("Won't test this combination as it's an invalid rule")

    rule = Rule(
        context=context,
        subject=subject,
        start=start,
        frequency_ordinal=ordinal,
        frequency_modifier=modifier,
    )
    with translation.override("en"):
        rule_as_text_en = rule.as_text()
    with translation.override("fi"):
        rule_as_text_fi = rule.as_text()

    assert rule_as_text_en
    assert rule_as_text_fi
    assert rule_as_text_en != rule_as_text_fi


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_resource_date_periods_as_text_is_kept_up_to_date(resource, lang):
    assert resource.date_periods_as_text == ""

    date_period = DatePeriodFactory(
        name="Test hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    assert resource.date_periods_as_text == (
        "\n========================================\n"
        "Test hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Auki\n"
        "\n"
        "========================================\n"
    )

    date_period.resource_state = State.CLOSED
    date_period.save()

    assert resource.date_periods_as_text == (
        "\n========================================\n"
        "Test hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Suljettu\n"
        "\n"
        "========================================\n"
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        weekdays=[Weekday.MONDAY],
        resource_state=State.OPEN,
    )

    assert resource.date_periods_as_text == (
        "\n========================================\n"
        "Test hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Maanantai 10.00-12.00 Auki\n"
        "\n"
        "========================================\n"
    )

    RuleFactory(
        group=time_span_group,
        context=RuleContext.PERIOD,
        subject=RuleSubject.WEEK,
        frequency_ordinal=2,
    )
    assert resource.date_periods_as_text == (
        "\n========================================\n"
        "Test hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Maanantai 10.00-12.00 Auki\n"
        "\n"
        " Voimassa kun kaikki seuraavat pätevät:\n"
        " - Jakson joka 2. viikko\n"
        "\n"
        "========================================\n"
    )


@pytest.mark.django_db
def test_text_updates_when_date_period_is_added_via_api(resource, admin_client):
    date_period_data = {
        "resource": resource.id,
        "name": {"fi": "Regular opening hours", "sv": None, "en": None},
        "start_date": "2021-01-01",
        "end_date": "2022-12-31",
        "resource_state": "open",
        "time_span_groups": [
            {
                "time_spans": [
                    {
                        "start_time": "09:00:00",
                        "end_time": "17:00:00",
                        "weekdays": [1, 2, 4],
                    },
                    {
                        "start_time": "09:00:00",
                        "end_time": "19:00:00",
                        "weekdays": [5, 6],
                    },
                    {
                        "start_time": "10:00:00",
                        "end_time": "14:00:00",
                        "weekdays": [7],
                    },
                ],
            }
        ],
    }

    assert resource.date_periods_as_text == ""

    url = reverse("date_period-list")

    response = admin_client.post(
        url,
        data=json.dumps(date_period_data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 201

    resource.refresh_from_db()

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Maanantai-Tiistai, Torstai 9.00-17.00 Auki\n"
        " Perjantai-Lauantai 9.00-19.00 Auki\n"
        " Sunnuntai 10.00-14.00 Auki\n"
        "\n"
        "========================================\n"
    )


@pytest.mark.django_db
def test_text_updates_when_timespan_is_removed_via_api(resource, admin_client):
    date_period = DatePeriodFactory(
        name="Regular opening hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span",
        group=time_span_group,
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=17, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.THURSDAY],
    )
    TimeSpanFactory(
        name="Test time span 2",
        group=time_span_group,
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=19, minute=0),
        weekdays=[Weekday.FRIDAY, Weekday.SATURDAY],
    )

    TimeSpanFactory(
        name="Test time span 3",
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        weekdays=[Weekday.SUNDAY],
    )

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Maanantai-Tiistai, Torstai 9.00-17.00 Auki\n"
        " Perjantai-Lauantai 9.00-19.00 Auki\n"
        " Sunnuntai 10.00-14.00 Auki\n"
        "\n"
        "========================================\n"
    )

    url = reverse("date_period-detail", kwargs={"pk": date_period.id})

    serializer = DatePeriodSerializer(instance=date_period)
    data = serializer.data

    del data["time_span_groups"][0]["time_spans"][0]

    response = admin_client.patch(
        url,
        data=json.dumps(data, cls=DjangoJSONEncoder),
        content_type="application/json",
    )

    assert response.status_code == 200

    resource.refresh_from_db()

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Perjantai-Lauantai 9.00-19.00 Auki\n"
        " Sunnuntai 10.00-14.00 Auki\n"
        "\n"
        "========================================\n"
    )


@pytest.mark.django_db
def test_date_period_as_text_with_time_span_description(resource):
    date_period = DatePeriodFactory(
        name="Regular opening hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span",
        group=time_span_group,
        start_time=datetime.time(hour=14, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.THURSDAY],
        description_fi="Naisten vuoro",
    )

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        ' Maanantai-Tiistai, Torstai 14.00-16.00 Auki "Naisten vuoro"\n'
        "\n"
        "========================================\n"
    )


@pytest.mark.django_db
def test_date_period_as_text_with_time_span_description_strip_special_chars(resource):
    date_period = DatePeriodFactory(
        name="Regular opening hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span",
        group=time_span_group,
        start_time=datetime.time(hour=14, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.THURSDAY],
        description_fi='Naisten\n//vu"oro',
    )

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        ' Maanantai-Tiistai, Torstai 14.00-16.00 Auki "Naisten vuoro"\n'
        "\n"
        "========================================\n"
    )


@pytest.mark.django_db
def test_date_period_as_text_with_time_span_resource_state_no_opening_hours(resource):
    date_period = DatePeriodFactory(
        name="Regular opening hours",
        resource=resource,
        resource_state=State.OPEN,
        start_date=datetime.date(year=2021, month=1, day=1),
        end_date=datetime.date(year=2022, month=12, day=31),
    )

    time_span_group = TimeSpanGroupFactory(period=date_period)

    TimeSpanFactory(
        name="Test time span 1",
        group=time_span_group,
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.THURSDAY],
    )

    TimeSpanFactory(
        name="Test time span 2",
        group=time_span_group,
        resource_state=State.NO_OPENING_HOURS,
        weekdays=[Weekday.WEDNESDAY],
    )

    TimeSpanFactory(
        name="Test time span 3",
        group=time_span_group,
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        weekdays=[Weekday.SATURDAY],
    )

    TimeSpanFactory(
        name="Test time span 4",
        group=time_span_group,
        resource_state=State.CLOSED,
        weekdays=[Weekday.SUNDAY],
    )

    assert resource.date_periods_as_text == (
        "\n"
        "========================================\n"
        "Regular opening hours\n"
        "Aikajakso: 1. tammikuuta 2021 - 31. joulukuuta 2022\n"
        "Aukioloajat:\n"
        "\n"
        " Maanantai-Tiistai, Torstai 8.00-16.00 Auki\n"
        " Lauantai 10.00-15.00 Auki\n"
        " Sunnuntai - Suljettu\n"
        "\n"
        "========================================\n"
    )
