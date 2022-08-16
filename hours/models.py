from __future__ import annotations

import datetime
import itertools
import re
from calendar import Calendar, monthrange
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import md5
from itertools import chain
from operator import attrgetter
from typing import List, Optional, Set, Union

from dateutil.relativedelta import SU, relativedelta
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import formats, translation
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from django_orghierarchy.models import Organization
from enumfields import EnumField, EnumIntegerField
from model_utils.models import SoftDeletableModel, TimeStampedModel
from timezone_field import TimeZoneField

from hours.enums import (
    FrequencyModifier,
    ResourceType,
    RuleContext,
    RuleSubject,
    State,
    Weekday,
)


@dataclass(order=True, frozen=True)
class TimeElement:
    """Represents one time span in a days opening hours

    The "end_time_on_next_day"-attribute is declared between the start and end time to
    allow TimeElements to sort correctly.

    The name, description, and periods attributes are ignored when comparing."""

    start_time: Optional[datetime.time]
    end_time_on_next_day: bool
    end_time: Optional[datetime.time]
    resource_state: State = State.UNDEFINED
    override: bool = False
    full_day: bool = False
    name: str = field(default="", compare=False)
    description: str = field(default="", compare=False)
    periods: Optional[list] = field(default=None, compare=False)
    # TODO: Add rules that matched
    # rules: Optional[list] = field(default=None, compare=False)

    def get_total_period_length(self) -> Optional[int]:
        """Total length of the periods in this element
        Returns None if there are no periods or one of the periods are unbounded"""
        if not self.periods:
            return None

        period_lengths = [p.get_period_length() for p in self.periods]
        if None in period_lengths:
            return None

        return sum(period_lengths)

    def get_next_day_part(self) -> Optional[TimeElement]:
        """Get the next day part of this time span
        Returns a new TimeElement with start time set to midnight, or None if
        this time span doesn't pass midnight."""
        if not self.end_time_on_next_day:
            return None

        return TimeElement(
            start_time=datetime.time(hour=0, minute=0),
            end_time=self.end_time,
            end_time_on_next_day=False,
            resource_state=self.resource_state,
            override=self.override,
            full_day=self.full_day,
            name=self.name,
            description=self.description,
            periods=self.periods,
        )


def get_range_overlap(start1, end1, start2, end2):
    min_end = min(end1, end2) if end1 and end2 else end1 or end2
    max_start = max(start1, start2) if start1 and start2 else start1 or start2

    return (
        max_start if min_end >= max_start else None,
        min_end if max_start <= min_end else None,
    )


def expand_range(start_date, end_date):
    if end_date < start_date:
        raise ValueError("Start must be before end")

    date_delta = end_date - start_date

    dates = []
    for i in range(date_delta.days + 1):
        dates.append(start_date + datetime.timedelta(days=i))

    return dates


def _get_times_for_sort(item: TimeElement) -> tuple:
    return (
        item.start_time if item.start_time else datetime.time.min,
        item.end_time_on_next_day,
        item.end_time if item.end_time else datetime.time.max,
    )


def combine_element_time_spans(elements, override=False):
    """Combines overlapping time elements

    Combines overlapping time spans to one time span if they are of the same resource
    state and same override status. By default, only returns spans with override=False.

    If one of the elements has unknown (empty) start or end, the corresponding time
    will be empty in the combined time element.
    """
    result = []

    states = {el.resource_state for el in elements if el.override == override}

    for state in states:
        state_elements = [el for el in elements if el.resource_state == state]

        # This will return those with start_time None first.
        # Other fields being equal, this will return those with end_time None last.
        sorted_elements = sorted(state_elements, key=_get_times_for_sort)

        new_range_start = None
        new_range_end = None
        new_range_end_is_next_day = False
        periods = set()

        for element in sorted_elements:
            if not element.start_time and not element.end_time:
                # Unknown range element found, no need to go through the others
                new_range_start = None
                new_range_end = None
                periods = element.periods if element.periods else []
                break

            # Compare using tuple (is_next_day, time_of_day) so that the next
            # day times are bigger even if the time_of_day is smaller.
            if (
                element.start_time
                and new_range_end
                and (new_range_end_is_next_day, new_range_end)
                >= (
                    False,
                    element.start_time,
                )
            ):
                # Ranges overlap! Previous end > this start
                if element.end_time:
                    # Element has specified end
                    latest_time = max(
                        (element.end_time_on_next_day, element.end_time),
                        (new_range_end_is_next_day, new_range_end),
                    )
                    new_range_end = latest_time[1]
                    new_range_end_is_next_day = latest_time[0]
                else:
                    # We don't know the end time
                    new_range_end = None
                    # what does this even mean? ends at end of next day?
                    new_range_end_is_next_day = element.end_time_on_next_day
            elif new_range_start or new_range_end:
                # Previous range ended before this starts!
                result.append(
                    TimeElement(
                        start_time=new_range_start,
                        end_time=new_range_end,
                        end_time_on_next_day=new_range_end_is_next_day,
                        resource_state=state,
                        override=override,
                        full_day=False,
                        periods=list(periods),
                    )
                )
                new_range_start = element.start_time
                new_range_end = element.end_time
                new_range_end_is_next_day = element.end_time_on_next_day
                periods = set()
            else:
                # start and end are empty, we are on first round
                new_range_start = element.start_time
                new_range_end = element.end_time
                new_range_end_is_next_day = element.end_time_on_next_day
            if element.periods:
                periods.update(element.periods)

        # appending last element
        result.append(
            TimeElement(
                start_time=new_range_start,
                end_time=new_range_end,
                end_time_on_next_day=new_range_end_is_next_day,
                resource_state=state,
                override=override,
                full_day=element.full_day,
                periods=list(periods),
            )
        )

    return result


def _time_element_period_length(time_element) -> int:
    """Returns total period length for sorting
    Handles unbounded periods by using 9999 as the period length"""
    total_period_length = time_element.get_total_period_length()
    return total_period_length if total_period_length is not None else 9999


def combine_and_apply_override(elements):
    """Combines the supplied elements by state and handles overrides"""
    overriding_elements = [el for el in elements if el.override]

    # Return only the overriding elements that have the same periods as the one that
    # is from the shortest period
    if len(overriding_elements) > 0:
        time_element = sorted(overriding_elements, key=_time_element_period_length)[0]
        periods = time_element.periods

        return combine_element_time_spans(
            [el for el in overriding_elements if el.periods == periods], override=True
        )
    return combine_element_time_spans(elements)


class DataSource(SoftDeletableModel, TimeStampedModel):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    user_editable_organizations = models.BooleanField(
        default=False, verbose_name=_("Organizations may be edited by users")
    )
    user_editable_resources = models.BooleanField(
        default=True, verbose_name=_("Resources may be edited by users")
    )

    class Meta:
        verbose_name = _("Data source")
        verbose_name_plural = _("Data sources")

    def __str__(self):
        return self.id


def get_resource_default_timezone():
    """Return the value of RESOURCE_DEFAULT_TIMEZONE setting

    Used in the default value of Resource.timezone to prevent the setting
    triggering a database migration every time the setting is changed."""
    return settings.RESOURCE_DEFAULT_TIMEZONE


class Resource(SoftDeletableModel, TimeStampedModel):
    name = models.CharField(
        verbose_name=_("Name"), max_length=255, null=True, blank=True
    )
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    address = models.TextField(verbose_name=_("Street address"), null=True, blank=True)
    resource_type = EnumField(
        ResourceType,
        verbose_name=_("Resource type"),
        max_length=100,
        default=ResourceType.UNIT,
    )
    children = models.ManyToManyField(
        "self",
        verbose_name=_("Sub resources"),
        related_name="parents",
        blank=True,
        symmetrical=False,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="resources",
        db_index=True,
        null=True,
        blank=True,
    )
    data_sources = models.ManyToManyField(DataSource, through="ResourceOrigin")
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
    )
    extra_data = models.JSONField(verbose_name=_("Extra data"), null=True, blank=True)
    is_public = models.BooleanField(default=True)
    timezone = TimeZoneField(
        default=get_resource_default_timezone, null=True, blank=True
    )
    # Denormalized values from the date periods
    date_periods_hash = models.CharField(max_length=64, null=True, blank=True)
    date_periods_as_text = models.TextField(null=True, blank=True)
    # Denormalized values from the parent resources
    ancestry_is_public = models.BooleanField(null=True, blank=True)
    ancestry_data_source = ArrayField(
        models.CharField(max_length=255),
        null=True,
        blank=True,
    )
    ancestry_organization = ArrayField(
        models.CharField(max_length=255),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Resource")
        verbose_name_plural = _("Resources")
        indexes = (models.Index(fields=["created"]), models.Index(fields=["modified"]))

    def __str__(self):
        return str(self.name)

    @property
    def _history_user(self):
        return self.last_modified_by

    @_history_user.setter
    def _history_user(self, value):
        self.last_modified_by = value

    def _get_date_periods_as_hash(self):
        date_period_hash_inputs = [
            date_period.as_hash_input()
            for date_period in self.date_periods.all().prefetch_related(
                "time_span_groups",
                "time_span_groups__time_spans",
                "time_span_groups__rules",
            )
            if not date_period.is_removed
        ]
        date_period_hash_inputs.sort()

        return md5("".join(date_period_hash_inputs).encode("utf8")).hexdigest()  # nosec

    def _get_date_periods_as_text(self):
        date_periods = [
            date_period
            for date_period in self.date_periods.all().prefetch_related(
                "time_span_groups",
                "time_span_groups__time_spans",
                "time_span_groups__rules",
            )
            if not date_period.is_removed
        ]

        if not date_periods:
            return ""

        separator = pgettext(
            "periods_as_text_separator", "\n========================================\n"
        )
        date_periods = separator.join(
            [date_period.as_text() for date_period in date_periods]
        )

        return _("{separator}{date_periods}{separator}").format(
            date_periods=date_periods,
            separator=separator,
        )

    def get_daily_opening_hours(self, start_date, end_date):
        # TODO: This is just an MVP. Things yet to do:
        #       - Support full_day

        all_daily_opening_hours = defaultdict(list)

        # Need to get one day before the start to handle cases where the previous days
        # opening hours extend to the next day.
        start_minus_one_day = start_date - relativedelta(days=1)

        # We can't filter the date_periods queryset here because we
        # want to allow the callers to use prefetch_related.
        for period in self.date_periods.all():
            # Filter the dates in code instead
            if period.start_date is not None and period.start_date > end_date:
                continue

            if period.end_date is not None and period.end_date < start_date:
                continue

            period_daily_opening_hours = period.get_daily_opening_hours(
                start_minus_one_day, end_date
            )
            for the_date, time_items in period_daily_opening_hours.items():
                all_daily_opening_hours[the_date].extend(time_items)

        days = list(all_daily_opening_hours.keys())
        days.sort()

        processed_opening_hours = {}
        for day in days:
            previous_day = day - relativedelta(days=1)

            # Add the time spans that might extend from the previous day to the
            # daily opening hours list for them to be considered in the combining step.
            for el in processed_opening_hours.get(previous_day, []):
                if not el.end_time_on_next_day:
                    continue

                all_daily_opening_hours[day].append(el.get_next_day_part())

            processed_opening_hours[day] = combine_and_apply_override(
                all_daily_opening_hours[day]
            )

        # Remove the excessive day from the start
        if start_minus_one_day in processed_opening_hours:
            del processed_opening_hours[start_minus_one_day]

        return processed_opening_hours

    def _get_parent_data(self, acc=None):
        if acc is None:
            acc = {
                "is_public": None,
                "data_sources": set(),
                "organizations": set(),
            }

        parents = (
            self.parents.all()
            .select_related("organization")
            .prefetch_related(
                "origins",
                "origins__data_source",
            )
        )

        if not parents:
            return acc

        for parent in parents:
            if acc["is_public"] is None:
                acc["is_public"] = parent.is_public

            if not parent.is_public:
                acc["is_public"] = False

            acc["data_sources"].update([i.data_source.id for i in parent.origins.all()])
            if parent.organization:
                acc["organizations"].add(parent.organization.id)

            parent._get_parent_data(acc)

        return acc

    def update_ancestry(self, update_child_ancestry_fields=True):
        data = self._get_parent_data()

        self.ancestry_is_public = data["is_public"]
        self.ancestry_data_source = list(data["data_sources"])
        self.ancestry_organization = list(data["organizations"])
        self.save(update_child_ancestry_fields=update_child_ancestry_fields)

    def update_denormalized_date_periods_data(self):
        self.date_periods_hash = self._get_date_periods_as_hash()
        # TODO: Save text in all languages
        with translation.override("fi"):
            self.date_periods_as_text = self._get_date_periods_as_text()

        self.save(
            update_fields=["date_periods_hash", "date_periods_as_text"],
            update_child_ancestry_fields=False,
        )

    def save(
        self,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
        update_child_ancestry_fields=True,
    ):
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

        if update_child_ancestry_fields:
            for child in self.children.all():
                child.update_ancestry()

    def get_ancestors(self, acc=None):
        if acc is None:
            acc = set()

        parents = self.parents.all()

        if not parents:
            return acc

        for parent in parents:
            if parent == self or parent in acc:
                continue

            acc.add(parent)
            parent.get_ancestors(acc)

        return acc

    def get_descendants(self, acc=None):
        if acc is None:
            acc = set()

        children = self.children.all()

        if not children:
            return acc

        for child in children:
            if child == self or child in acc:
                continue

            acc.add(child)
            child.get_descendants(acc)

        return acc

    def copy_all_periods_to_resource(self, target_resource, replace=False):
        if (
            not target_resource
            or not isinstance(target_resource, Resource)
            or self.id == target_resource.id
        ):
            return

        existing_period_ids = []
        if replace:
            existing_period_ids = list(
                target_resource.date_periods.all().values_list("id", flat=True)
            )

        def copy_instance(instance, foreign_field_name=None, foreign_instance=None):
            new_instance = deepcopy(instance)
            new_instance.id = None
            if foreign_field_name and foreign_instance:
                setattr(new_instance, foreign_field_name, foreign_instance)
            new_instance.save()

            return new_instance

        for period in self.date_periods.all():
            new_period = copy_instance(period, "resource", target_resource)

            for time_span_group in period.time_span_groups.all():
                new_time_span_group = copy_instance(
                    time_span_group, "period", new_period
                )

                for time_span in time_span_group.time_spans.all():
                    copy_instance(time_span, "group", new_time_span_group)

                for rule in time_span_group.rules.all():
                    copy_instance(rule, "group", new_time_span_group)

        if replace:
            # Mark target's old periods deleted
            for period in target_resource.date_periods.filter(
                id__in=existing_period_ids
            ):
                period.delete()


class ResourceOrigin(models.Model):
    resource = models.ForeignKey(
        Resource, related_name="origins", on_delete=models.CASCADE
    )
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    origin_id = models.CharField(
        verbose_name=_("Origin ID"), max_length=100, db_index=True
    )

    class Meta:
        verbose_name = _("Resource origin")
        verbose_name_plural = _("Resource origins")
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "origin_id"],
                name="unique_identifier_per_data_source",
            ),
        ]

    def __str__(self):
        return f"{self.data_source}:{self.origin_id}"


class DatePeriod(SoftDeletableModel, TimeStampedModel):
    resource = models.ForeignKey(
        Resource, on_delete=models.PROTECT, related_name="date_periods", db_index=True
    )
    name = models.CharField(
        verbose_name=_("Name"), max_length=255, null=True, blank=True
    )
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    start_date = models.DateField(
        verbose_name=_("Start date"), null=True, blank=True, db_index=True
    )
    end_date = models.DateField(
        verbose_name=_("End date"), null=True, blank=True, db_index=True
    )
    resource_state = EnumField(
        State,
        verbose_name=_("Resource state"),
        max_length=100,
        default=State.UNDEFINED,
    )
    override = models.BooleanField(
        verbose_name=_("Override"), default=False, db_index=True
    )
    data_sources = models.ManyToManyField(DataSource, through="PeriodOrigin")
    is_public = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Period")
        verbose_name_plural = _("Periods")
        ordering = ["start_date"]
        indexes = (models.Index(fields=["created"]), models.Index(fields=["modified"]))

    def __str__(self):
        return f"{self.name}({self.start_date} - {self.end_date} {self.resource_state})"

    def as_hash_input(self) -> str:
        data = "[DATE_PERIOD:{}]".format(
            "|".join(
                [
                    self.start_date.isoformat() if self.start_date else "*",
                    self.end_date.isoformat() if self.end_date else "*",
                    str(self.resource_state.value),
                    str(self.override),
                ]
            )
        )

        group_strings = []
        for time_span_group in self.time_span_groups.all():
            if time_span_group.is_removed:
                continue
            group_strings.append(time_span_group.as_hash_input())
        group_strings.sort()

        return data + "".join(group_strings)

    def as_text(self) -> str:
        group_strings = []
        for time_span_group in self.time_span_groups.all():
            if time_span_group.is_removed:
                continue
            if not time_span_group.time_spans.count():
                continue
            group_strings.append(time_span_group.as_text())

        if not group_strings and self.resource_state != State.UNDEFINED:
            group_strings = [" " + str(self.resource_state)]

        time_span_groups = _("\n\n ---------------------------------------\n\n").join(
            group_strings
        )

        dates = _("Not specified")
        if self.start_date or self.end_date:
            if self.start_date == self.end_date:
                dates = formats.date_format(self.start_date)
            else:
                dates = "{start_date} - {end_date}".format(
                    start_date=formats.date_format(self.start_date)
                    if self.start_date
                    else "",
                    end_date=formats.date_format(self.end_date)
                    if self.end_date
                    else "",
                )

        return _(
            "{name}{description}Date period: {dates}\n"
            "Opening hours:\n\n"
            "{time_span_groups}\n"
        ).format(
            name=self.name + "\n" if self.name else "",
            description=self.description + "\n" if self.description else "",
            dates=dates,
            time_span_groups=time_span_groups,
        )

    def get_daily_opening_hours(self, start_date, end_date):
        overlap = get_range_overlap(
            start_date, end_date, self.start_date, self.end_date
        )

        range_dates = set(expand_range(overlap[0], overlap[1]))
        result = defaultdict(list)
        time_span_groups = self.time_span_groups.all()

        # Return all days as full days if the period has no time spans
        if not time_span_groups:
            if self.resource_state != State.UNDEFINED:
                for one_date in range_dates:
                    result[one_date].append(
                        TimeElement(
                            start_time=None,
                            end_time=None,
                            end_time_on_next_day=False,
                            resource_state=self.resource_state,
                            override=self.override,
                            full_day=True,
                            name=self.name,
                            description=self.description,
                            periods=[self],
                        )
                    )
            return result

        result_dates = set(expand_range(overlap[0], overlap[1]))

        for time_span_group in time_span_groups:
            rules = time_span_group.rules.all()
            time_spans = time_span_group.time_spans.all()
            result_dates_per_group = result_dates.copy()

            if rules.count():
                for rule in rules:
                    matching_dates = rule.apply_to_date_range(overlap[0], overlap[1])
                    result_dates_per_group &= matching_dates

            for one_date in result_dates_per_group:
                for time_span in time_spans:
                    if (
                        not time_span.weekdays
                        or Weekday.from_iso_weekday(one_date.isoweekday())
                        in time_span.weekdays
                    ):
                        resource_state = self.resource_state
                        if time_span.resource_state != State.UNDEFINED:
                            resource_state = time_span.resource_state

                        # TODO: add matching rules to the TimeElement
                        result[one_date].append(
                            TimeElement(
                                start_time=time_span.start_time,
                                end_time=time_span.end_time,
                                end_time_on_next_day=time_span.end_time_on_next_day,
                                resource_state=resource_state,
                                override=self.override,
                                full_day=time_span.full_day,
                                name=time_span.name,
                                description=time_span.description,
                                periods=[self],
                            )
                        )

        return result

    def get_period_length(self) -> Optional[int]:
        """Get the length of this period in days
        Returns None if the period is unbounded."""
        if not self.start_date or not self.end_date:
            # Unbounded, can't know the length
            return None

        return (self.end_date - self.start_date).days


class PeriodOrigin(models.Model):
    period = models.ForeignKey(
        DatePeriod, related_name="origins", on_delete=models.CASCADE
    )
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    origin_id = models.CharField(
        verbose_name=_("Origin ID"), max_length=100, db_index=True
    )

    class Meta:
        verbose_name = _("Period origin")
        verbose_name_plural = _("Period origins")
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "origin_id"],
                name="unique_period_identifier_per_data_source",
            ),
        ]

    def __str__(self):
        return f"{self.data_source}:{self.origin_id}"


class TimeSpanGroup(SoftDeletableModel, models.Model):
    period = models.ForeignKey(
        DatePeriod, on_delete=models.PROTECT, related_name="time_span_groups"
    )

    def __str__(self):
        return f"{self.period} time spans {self.time_spans.all()}"

    def as_hash_input(self) -> str:
        time_span_strings = []
        for time_span in self.time_spans.all():
            if time_span.is_removed:
                continue
            time_span_strings.append(time_span.as_hash_input())
        time_span_strings.sort()

        rule_strings = []
        for rule in self.rules.all():
            if rule.is_removed:
                continue
            rule_strings.append(rule.as_hash_input())
        rule_strings.sort()

        return "".join(time_span_strings + rule_strings)

    def as_text(self) -> str:
        rule_strings = []
        for rule in self.rules.all():
            if rule.is_removed:
                continue
            rule_strings.append(" - " + rule.as_text())

        time_span_strings = []
        for time_span in self.time_spans.all():
            if time_span.is_removed:
                continue
            time_span_strings.append(" " + time_span.as_text())

        result = "\n".join(time_span_strings)
        if rule_strings:
            result += _("\n\n In effect when every one of these match:\n") + "\n".join(
                rule_strings
            )

        return result


class TimeSpan(SoftDeletableModel, TimeStampedModel):
    group = models.ForeignKey(
        TimeSpanGroup, on_delete=models.PROTECT, related_name="time_spans"
    )
    name = models.CharField(
        verbose_name=_("Name"), max_length=255, null=True, blank=True
    )
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    start_time = models.TimeField(
        verbose_name=_("Start time"), null=True, blank=True, db_index=True
    )
    end_time = models.TimeField(
        verbose_name=_("End time"), null=True, blank=True, db_index=True
    )
    end_time_on_next_day = models.BooleanField(
        verbose_name=_("Is end time on the next day"), default=False
    )
    full_day = models.BooleanField(verbose_name=_("24 hours"), default=False)
    weekdays = ArrayField(
        EnumIntegerField(
            Weekday,
            verbose_name=_("Weekday"),
            default=None,
        ),
        null=True,
        blank=True,
    )
    resource_state = EnumField(
        State,
        verbose_name=_("Resource state"),
        max_length=100,
        default=State.UNDEFINED,
    )

    class Meta:
        verbose_name = _("Time span")
        verbose_name_plural = _("Time spans")
        ordering = [
            "weekdays",
            "start_time",
            "end_time_on_next_day",
            "end_time",
            "resource_state",
        ]

    def __str__(self):
        if self.weekdays:
            weekdays = ", ".join([str(i) for i in self.weekdays])
        else:
            weekdays = "[no weekdays]"

        return f"{self.name}({self.start_time} - {self.end_time} {weekdays})"

    def as_hash_input(self) -> str:
        sorted_weekdays = []
        if self.weekdays:
            sorted_weekdays = sorted(self.weekdays, key=attrgetter("value"))

        return "[TIME_SPAN:{}]".format(
            "|".join(
                [
                    self.start_time.isoformat() if self.start_time else "*",
                    self.end_time.isoformat() if self.end_time else "*",
                    str(self.end_time_on_next_day),
                    str(self.full_day),
                    "".join([str(i.value) for i in sorted_weekdays])
                    if self.weekdays
                    else "*",
                    str(self.resource_state.value),
                ]
            )
        )

    def get_weekdays_as_text(self) -> str:
        if not self.weekdays:
            return pgettext("timespan_as_text", "Every day")

        sorted_weekdays = sorted(self.weekdays, key=attrgetter("value"))

        weekday_strings = []
        for k, group in itertools.groupby(
            sorted_weekdays, lambda w, c=itertools.count(): w.value - next(c)
        ):
            consecutive_weekdays = list(group)
            if len(consecutive_weekdays) > 1:
                weekday_strings.append(
                    str(consecutive_weekdays[0]) + "-" + str(consecutive_weekdays[-1])
                )
            else:
                weekday_strings.append(str(consecutive_weekdays[0]))

        weekdays_text = ", ".join(weekday_strings)

        return weekdays_text

    def as_text(self) -> str:
        if self.resource_state == State.UNDEFINED:
            state = self.group.period.resource_state.label
        else:
            state = self.resource_state.label

        if self.full_day:
            times = pgettext("timespan_as_text", "The whole day")
        else:
            times = pgettext("timespan_as_text", "{start_time}-{end_time}").format(
                start_time=formats.time_format(self.start_time)
                if self.start_time
                else "",
                end_time=formats.time_format(self.end_time) if self.end_time else "",
            )
        return pgettext("timespan_as_text", "{weekdays} {times} {state}").format(
            state=state,
            weekdays=self.get_weekdays_as_text(),
            times=times,
        )


class Rule(SoftDeletableModel, TimeStampedModel):
    group = models.ForeignKey(
        TimeSpanGroup, on_delete=models.PROTECT, related_name="rules"
    )
    name = models.CharField(
        verbose_name=_("Name"), max_length=255, null=True, blank=True
    )
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    context = EnumField(
        RuleContext,
        verbose_name=_("Context"),
        max_length=100,
    )
    subject = EnumField(
        RuleSubject,
        verbose_name=_("Subject"),
        max_length=100,
    )
    start = models.IntegerField(verbose_name=_("Start"), null=True, blank=True)
    frequency_ordinal = models.PositiveIntegerField(
        verbose_name=_("Frequency (ordinal)"), null=True, blank=True
    )
    frequency_modifier = EnumField(
        FrequencyModifier,
        verbose_name=_("Frequency (modifier)"),
        max_length=100,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Rule")
        verbose_name_plural = _("Rules")

    def __str__(self):
        if self.frequency_modifier:
            return f"{self.frequency_modifier} {self.subject}s in {self.context}"
        else:
            return (
                f"every {self.frequency_ordinal} {self.subject}s in "
                f"{self.context}, starting from {self.start}"
            )

    def as_hash_input(self) -> str:
        return "[RULE:{}]".format(
            "|".join(
                [
                    self.context.value if self.context else "*",
                    self.subject.value if self.subject else "*",
                    str(self.start) if self.start is not None else "*",
                    str(self.frequency_ordinal)
                    if self.frequency_ordinal is not None
                    else "*",
                    self.frequency_modifier.value
                    if self.frequency_modifier is not None
                    else "*",
                ]
            )
        )

    def as_text(self) -> str:
        if self.context == RuleContext.PERIOD:
            context_text = pgettext("rule_as_text_context", "the period")
        else:
            context_text = pgettext("rule_as_text_context", "every {context}").format(
                context=pgettext("every_rulecontext", self.context.value)
            )

        text = ""
        if self.start and not self.frequency_ordinal and not self.frequency_modifier:
            text = pgettext("rule_as_text", "{nth} {subject} in {context}").format(
                nth=ordinal(self.start),
                subject=self.subject.label.lower(),
                context=context_text,
            )
        elif self.frequency_ordinal:
            starting_from_text = ""
            if self.start is not None and self.start != 1:
                starting_from_text = pgettext(
                    "rule_as_text", "starting from the {nth} {last} {subject}"
                ).format(
                    nth=ordinal(abs(self.start)) if self.start != -1 else "",
                    last=pgettext("starting_from_the_last", "last")
                    if self.start < 0
                    else "",
                    subject=pgettext(
                        "starting_from_nth_rulesubject", self.subject.value
                    ),
                )

            text = pgettext(
                "rule_as_text",
                "Every {nth} {subject} in {context} {starting_from_text}",
            ).format(
                nth=ordinal(self.frequency_ordinal)
                if self.frequency_ordinal != 1
                else "",
                subject=self.subject.label.lower(),
                context=context_text,
                starting_from_text=starting_from_text,
            )
        elif self.frequency_modifier:
            text = pgettext(
                "rule_as_text", "On {modifier} {subject}s in {context}"
            ).format(
                modifier=self.frequency_modifier.label.lower(),
                subject=self.subject.label.lower(),
                context=context_text,
            )
        return re.sub(r"\s{2,}", " ", text.rstrip())

    def save(self, *args, **kwargs):
        # Note that save is not called if rules are created in the database with bulk
        # or update operations, so the database may still contain non-functional rules.
        # Cleaning here is just a precaution that tells the user not to create
        # useless/vague rules, since they most likely want to be informed if their
        # fancy new rule doesn't do anything.
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not self.group.period.start_date and self.context == RuleContext.PERIOD:
            raise ValidationError(
                _(
                    "We cannot start counting from period start in an infinite"
                    " period. Please select shorter context for your rule."
                )
            )
        if self.context == RuleContext.MONTH and self.subject == RuleSubject.MONTH:
            raise ValidationError(_("Subject must be a shorter timespan than context."))
        if self.frequency_modifier and self.frequency_ordinal:
            raise ValidationError(
                _(
                    "You cannot add a rule with both even/odd and another frequency"
                    " at the same time."
                )
            )
        if self.start == 0 and not (
            self.subject == RuleSubject.WEEK and self.context == RuleContext.YEAR
        ):
            raise ValidationError(
                _(
                    "Rule can only start from zero if starting from zeroth ISO week"
                    " of the year. All other rules start counting from 1. Use negative"
                    " numbers to count from the end of the context."
                )
            )
        if self.start and self.frequency_modifier:
            raise ValidationError(
                _(
                    "Even/odd subjects are not counted starting from a specific time."
                    " If you wish to have an alternating rule starting from a specific"
                    " time, please use frequency_ordinal=2 with start=1 or start=2."
                )
            )
        if self.frequency_ordinal and not self.start:
            self.start = 1
        return super().clean()

    def get_ordinal_for_item(
        self, item: Union[List[datetime.date], datetime.date]
    ) -> Union[None, int]:
        """Return ordinal for the provided context item"""
        if not item:
            return None

        # TODO: Is checking the first item sufficient?
        if isinstance(item, list):
            item = item[0]

        if self.subject.is_singular():
            return item.day
        if self.subject == RuleSubject.WEEK:
            return item.isocalendar()[1]
        if self.subject == RuleSubject.MONTH:
            return item.month

    def _filter_context_set(self, context_set: list) -> list:
        """Filter the provided context set by start and frequency"""
        if not self.frequency_modifier and not self.frequency_ordinal:
            if self.start is None:
                return context_set
            try:
                if (
                    self.subject == RuleSubject.WEEK
                    and self.context == RuleContext.YEAR
                    and context_set[0][6].day < 4
                ):
                    # iso week 1 is the week with Thu. If the first week doesn't
                    # contain Thu, count starts from zeroth week.
                    return [context_set[self.start]]
                return [context_set[self.start if self.start < 0 else self.start - 1]]
            except IndexError:
                return []

        if self.frequency_ordinal:
            if self.start is None:
                # Start should be set to 1 as default. If rule was created by
                # unorthodox means and start is empty, just do nothing
                return context_set
            if self.context == RuleContext.PERIOD and not self.group.period.start_date:
                # Again, this rule doesn't do anything, but better let it slip thru.
                return context_set
            try:
                if (
                    self.subject == RuleSubject.WEEK
                    and self.context == RuleContext.YEAR
                    and context_set[0][6].day < 4
                ):
                    # iso week 1 is the week with Thu. If the first week doesn't
                    # contain Thu, count starts from zeroth week.
                    return context_set[self.start :: self.frequency_ordinal]
                return context_set[
                    self.start
                    if self.start < 0
                    else self.start - 1 :: self.frequency_ordinal
                ]
            except IndexError:
                return []
        elif self.frequency_modifier:
            if self.context == RuleContext.PERIOD and not self.group.period.start_date:
                # Again, this rule doesn't do anything, but better let it slip thru.
                return context_set
            result = []
            for item in context_set:
                num = self.get_ordinal_for_item(item)
                if self.frequency_modifier == FrequencyModifier.EVEN and num % 2 == 0:
                    result.append(item)
                if self.frequency_modifier == FrequencyModifier.ODD and num % 2 == 1:
                    result.append(item)
            return result

    def get_context_sets(
        self, max_start_date: datetime.date, min_end_date: datetime.date
    ) -> List:
        """Get context sets defined by the Rules context and subject"""

        if self.context == RuleContext.PERIOD:
            # if period is bounded, start and end dates are already bounded by period
            period_start_date = self.group.period.start_date
            if not period_start_date:
                # Just return the queried set. Frequency modifiers won't do anything
                # in this case, as we cannot count from the start.
                period_start_date = max_start_date
            if self.subject == RuleSubject.DAY:
                return [expand_range(max_start_date, min_end_date)]

            elif self.subject == RuleSubject.WEEK:
                week_start = period_start_date - relativedelta(
                    days=period_start_date.weekday()
                )
                week_end = week_start + relativedelta(weekday=SU(1))

                weeks = []
                while week_start <= min_end_date:
                    weeks.append(expand_range(week_start, week_end))
                    week_start = week_start + relativedelta(weeks=1)
                    week_end = week_start + relativedelta(weekday=SU(1))

                return [weeks]

            elif self.subject == RuleSubject.MONTH:
                first_day = datetime.date(
                    year=period_start_date.year,
                    month=period_start_date.month,
                    day=1,
                )
                last_day_of_month = first_day + relativedelta(day=31)

                months = []
                while last_day_of_month <= min_end_date + relativedelta(day=31):
                    months.append(expand_range(first_day, last_day_of_month))
                    first_day += relativedelta(months=1)
                    last_day_of_month = first_day + relativedelta(day=31)

                return [months]

            elif self.subject in RuleSubject.weekday_subjects():
                dates = []
                for a_date in expand_range(period_start_date, min_end_date):
                    if a_date.isoweekday() == self.subject.as_isoweekday():
                        dates.append(a_date)

                return [dates]

        elif self.context == RuleContext.YEAR:
            years = range(max_start_date.year, min_end_date.year + 1)

            result = []
            for year in years:
                if self.subject == RuleSubject.DAY:
                    result.append(
                        expand_range(
                            datetime.date(year=year, month=1, day=1),
                            datetime.date(year=year, month=12, day=31),
                        )
                    )
                elif self.subject == RuleSubject.WEEK:
                    year_start_date = datetime.date(year=year, month=1, day=1)
                    week_start = year_start_date - relativedelta(
                        days=year_start_date.weekday()
                    )
                    week_end = week_start + relativedelta(weekday=SU(1))

                    weeks = []
                    while week_start <= min_end_date:
                        weeks.append(expand_range(week_start, week_end))
                        week_start = week_start + relativedelta(weeks=1)
                        week_end = week_start + relativedelta(weekday=SU(1))

                    result.append(weeks)
                elif self.subject == RuleSubject.MONTH:
                    months = []
                    for month_number in range(1, 13):
                        first_day_of_month = datetime.date(
                            year=year, month=month_number, day=1
                        )
                        last_day_of_month = first_day_of_month + relativedelta(day=31)
                        months.append(
                            expand_range(first_day_of_month, last_day_of_month)
                        )

                    result.append(months)
                elif self.subject in RuleSubject.weekday_subjects():
                    days_in_year = expand_range(
                        datetime.date(year=year, month=1, day=1),
                        datetime.date(year=year, month=12, day=31),
                    )
                    dates = []
                    for a_date in days_in_year:
                        if a_date.isoweekday() == self.subject.as_isoweekday():
                            dates.append(a_date)

                    result.append(dates)

            return result

        elif self.context == RuleContext.MONTH:
            c = Calendar()

            first_day = datetime.date(
                year=max_start_date.year, month=max_start_date.month, day=1
            )
            first_day_weekday, month_length = monthrange(
                first_day.year, first_day.month
            )
            last_day_of_month = first_day + relativedelta(day=month_length)

            result = []
            while last_day_of_month <= min_end_date + relativedelta(day=31):
                if self.subject == RuleSubject.DAY:
                    days_in_month = expand_range(first_day, last_day_of_month)
                    result.append(days_in_month)
                elif self.subject == RuleSubject.WEEK:
                    weeks_in_month = c.monthdatescalendar(
                        first_day.year, first_day.month
                    )
                    result.append(weeks_in_month)

                elif self.subject == RuleSubject.MONTH:
                    raise ValueError("Not applicable")

                elif self.subject in RuleSubject.weekday_subjects():
                    days_in_month = expand_range(first_day, last_day_of_month)

                    dates = []
                    for a_date in days_in_month:
                        if a_date.isoweekday() == self.subject.as_isoweekday():
                            dates.append(a_date)

                    result.append(dates)

                first_day += relativedelta(months=1)
                first_day_weekday, month_length = monthrange(
                    first_day.year, first_day.month
                )
                last_day_of_month = first_day + relativedelta(day=month_length)
            return result

    def apply_to_date_range(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> Set[datetime.date]:
        """Apply rule to the provided date range"""
        max_start_date = start_date
        if self.group.period.start_date:
            max_start_date = max(start_date, self.group.period.start_date)

        min_end_date = end_date
        if self.group.period.end_date:
            min_end_date = min(end_date, self.group.period.end_date)

        if max_start_date > min_end_date:
            # Period starts after the filter start date or the period ends before the
            # filter start date
            # TODO: Raise error?
            return set()

        matching_dates = set()

        # Get a set of dates that match the context and subject
        context_sets = self.get_context_sets(max_start_date, min_end_date)

        # Filter every set by start and frequency
        for context_set in context_sets:
            filtered_context_set = self._filter_context_set(context_set)
            # Flatten list of lists
            if any(isinstance(item, list) for item in filtered_context_set):
                filtered_context_set = chain(*filtered_context_set)

            matching_dates |= set(filtered_context_set)

        range_dates = set(expand_range(max_start_date, min_end_date))

        return matching_dates & range_dates


class SignedAuthEntry(models.Model):
    signature = models.TextField(verbose_name=_("Signature"))
    created_at = models.DateTimeField(verbose_name=_("Signature created at"))
    valid_until = models.DateTimeField(verbose_name=_("Signature valid until"))
    invalidated_at = models.DateTimeField(
        verbose_name=_("Invalidated time"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Signed auth entry")
        verbose_name_plural = _("Signed auth entries")


class SignedAuthKey(models.Model):
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    signing_key = models.TextField(verbose_name=_("Signing key"))
    valid_after = models.DateTimeField(verbose_name=_("Key valid after"))
    valid_until = models.DateTimeField(
        verbose_name=_("Key valid until"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Signed auth key")
        verbose_name_plural = _("Signed auth keys")

    def __str__(self):
        return f"SignedAuthKey {self.data_source.name}"
