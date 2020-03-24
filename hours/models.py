from django.db import models
from django.db.models import Count, F
from django.contrib.postgres.fields import DateRangeField
from django.contrib.postgres.indexes import GistIndex
from psycopg2.extras import DateTimeTZRange
import pandas as pd
import numpy as np

from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError
from hauki import settings


User = settings.AUTH_USER_MODEL

class Status(models.IntegerChoices):
    CLOSED = 0, _('closed')
    OPEN = 1, _('open')
    UNDEFINED = 2, _('undefined')


class Weekday(models.IntegerChoices):
    MONDAY = 1, _('Monday')
    TUESDAY = 2, _('Tuesday')
    WEDNESDAY = 3, _('Wednesday')
    THURSDAY = 4, _('Thursday')
    FRIDAY = 5, _('Friday')
    SATURDAY = 6, _('Saturday')
    SUNDAY= 7, _('Sunday')


class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=255)

    class Meta:
        verbose_name = _('Data source')
        verbose_name_plural = _('Data sources')

    def __str__(self):
        return self.id


class BaseModel(models.Model):
    id = models.CharField(max_length=100, primary_key=True)

    # Both fields are required
    data_source = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name='provided_%(class)s_data', db_index=True)
    origin_id = models.CharField(verbose_name=_('Origin ID'), max_length=100, db_index=True)

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    same_as = models.URLField(verbose_name=_('Same object as'), max_length=1000, null=True, blank=True)

    created_time = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    last_modified_time = models.DateTimeField(null=True, blank=True, auto_now=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_created_by")
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_modified_by")
    deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['data_source', 'origin_id'],
                                    name='%(app_label)s_%(class)s_origin_id_unique'),
        ]

    def __str__(self):
        return f'{self.name} ({self.id})'

    def save(self, *args, **kwargs):
        if not self.data_source:
            raise ValidationError(_("Data source is required."))
        if not self.origin_id:
            raise ValidationError(_("Origin ID is required."))
        if not self.id:
            self.id = f'{self.data_source_id}:{self.origin_id}'
        id_parts = self.id.split(':')
        if len(id_parts) < 2 or id_parts[0] != self.data_source_id or id_parts[1] != self.origin_id:
            raise ValidationError(_("Id must be of the format data_source:origin_id."))
        super().save(*args, **kwargs)


class Target(BaseModel):
    parent = models.ForeignKey('self', on_delete=models.PROTECT, related_name='first_children', db_index=True, null=True)
    second_parent = models.ForeignKey('self', on_delete=models.PROTECT, related_name='second_children', db_index=True, null=True)
    hours_updated = models.DateTimeField(null=True, blank=True, db_index=True)
    default_status = models.IntegerField(choices=Status.choices, default=Status.UNDEFINED)

    class Meta(BaseModel.Meta):
        verbose_name = _('Target')
        verbose_name_plural = _('Targets')

    def get_period_for_date(self, date):
        # returns the period that determines the opening hours for a given date, or None
        active_periods = self.periods.filter(period__contains=date)
        shortest_period = active_periods.first()
        if shortest_period:
            shortest_length = shortest_period.period.upper-shortest_period.period.lower
        for period in active_periods:
            # we have to evaluate the queryset (probably just a few objects)
            # because upper and lower are field properties, not fields
            length = period.period.upper-period.period.lower
            if length < shortest_length:
                shortest_period = period
                shortest_length = length
        return shortest_period


class Keyword(BaseModel):
    targets = models.ManyToManyField(Target, related_name='keywords', db_index=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('Keyword')
        verbose_name_plural = _('Keywords')


class Period(BaseModel):
    target = models.ForeignKey(Target, on_delete=models.PROTECT, related_name='periods', db_index=True)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN, db_index=True)
    period = DateRangeField()

    class Meta(BaseModel.Meta):
        verbose_name = _('Period')
        verbose_name_plural = _('Periods')
        indexes = [
            GistIndex(fields=['period'])
        ]
    
    def __str__(self):
        return f'{self.target}:{self.period})'


class Opening(models.Model):
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name='openings', db_index=True)
    weekday = models.IntegerField(choices=Weekday.choices)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN, db_index=True)
    opens = models.TimeField(db_index=True)
    closes = models.TimeField(db_index=True)
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    # by default, all openings are for the first week of the rule, i.e. rotation of 1 week
    week = models.IntegerField(verbose_name=_('Week number'), default=1)
    # by default, there is no monthly rule (only weekly rule), i.e. rotation of 0 months
    month = models.IntegerField(verbose_name=_('Month number'), default=0)

    def __str__(self):
        return f'{self.period}: {self.weekday} {self.opens}-{self.closes}'

    class Meta:
        verbose_name = _('Opening')
        verbose_name_plural = _('Openings')
