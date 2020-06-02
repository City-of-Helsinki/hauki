from datetime import timedelta
from collections import OrderedDict
from django.db import models
from django.db.models import Count, F, Max
from django.contrib.postgres.fields import DateRangeField
from django.contrib.postgres.indexes import GistIndex
from psycopg2.extras import DateRange
import pandas as pd
import numpy as np
import time

from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError
from hauki import settings


User = settings.AUTH_USER_MODEL

class Status(models.IntegerChoices):
    CLOSED = 0, _('closed')
    OPEN = 1, _('open')
    UNDEFINED = 2, _('undefined')
    SELF_SERVICE = 3, _('self_service')
    WITH_KEY = 4, _('with key')
    WITH_RESERVATION = 5, _('with reservation')
    WITH_KEY_AND_RESERVATION = 6, _('with key and reservation')
    ONLY_ENTERING = 7, _('only entering')
    ONLY_LEAVING = 8, _('only leaving')


class TargetType(models.IntegerChoices):
    UNIT = 0, _('unit')
    UNIT_SERVICE = 1, _('unit_service')
    SPECIAL_GROUP = 2, _('special_group')
    PERSON = 3, _('person')
    TELEPHONE = 4, _('telephone')
    SERVICE = 5, _('service')
    SERVICE_CHANNEL = 6, _('service_channel')
    SERVICE_AT_UNIT = 7, _('service_at_unit')
    RESOURCE = 8, _('resource')
    BUILDING = 9, _('building')
    AREA = 10, _('area')


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
    published = models.BooleanField(default=True)
    publication_time = models.DateTimeField(null=True, blank=True)

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
    target_type = models.IntegerField(choices=TargetType.choices, default=TargetType.UNIT)

    class Meta(BaseModel.Meta):
        verbose_name = _('Target')
        verbose_name_plural = _('Targets')

    def get_periods_for_range(self, start, end=None, include_drafts=False, period_type=None):
        """Returns the period that determines the opening hours for each date in the range, or None

        Parameters:
        start (date): Starting date for requested date range
        end (date): Ending date for requested date range. If omitted, only return one date.
        include_drafts (bool): Whether non-published periods are taken into account, for preview purposes
        period_type (string): Only consider 'normal' or 'override' periods, or None (considers both).

        Returns:
        OrderedDict[Period]: The period that determines opening hours for each date
        """
        if not end:
            # default only returns single day
            end = start
        potential_periods = self.periods.filter(period__overlap=DateRange(lower=start, upper=end, bounds='[]'))
        if period_type:
            if period_type=='normal':
                potential_periods.filter(override=False)
            if period_type=='override':
                potential_periods.filter(override=True)
        if not include_drafts:
            potential_periods = potential_periods.filter(published=True)
        periods = [p for p in potential_periods.prefetch_related('openings')] # 1 query + evaluate small QS, that's all we need
        # store the rotation metadata per period
        for period in periods:
            # Weekly rotation is subordinate to monthly rotation, if present.
            # max_month 0 means no monthly rotation (only weekly rotation)
            period.max_month = period.openings.aggregate(Max('month'))['month__max']
            # max_week 0 means no weekly rotation (only monthly rotation)
            period.max_week = period.openings.aggregate(Max('week'))['week__max']
        # shorter periods always take precedence
        periods.sort(key=lambda x: (-x.override, x.period.upper - x.period.lower))
        dates = pd.date_range(start, end).date
        active_periods = OrderedDict()  
        for date in dates:
            for period in periods:
                if date in period.period:
                    active_periods[date] = period
                    break
            else:
                active_periods[date] = None
        return active_periods

    def get_openings_for_range(self, start, end=None, include_drafts=False, period_type=None, period=None):
        """Returns the opening hours for each date in the range, or None

        Parameters:
        start (date): Starting date for requested date range
        end (date): Ending date for requested date range. If omitted, only return one date.
        include_drafts (bool): Whether non-published periods are taken into account, for preview purposes
        period_type (string): Only consider 'normal' or 'override' periods, or None (considers both).

        Returns:
        OrderedDict[Queryset[Opening]]: All the opening hours for each date
        """
        active_periods = self.get_periods_for_range(start, end, include_drafts=False, period_type=None)
        if not end:
            # default only returns single day
            end = start
        dates = pd.date_range(start, end).date
        openings = OrderedDict()
        for date in dates:
            if not active_periods[date]:
                openings[date] = Opening.objects.none()
                continue
            # get number of requested month since start of active period
            date_month_number = (date.year - active_periods[date].period.lower.year)*12 + date.month - active_periods[date].period.lower.month + 1
            # get number of requested month modulo repetition
            max_month = active_periods[date].max_month
            max_week = active_periods[date].max_week
            if max_month:
                # zero remainder is mapped to max_month (range is 1, 2,  ..., max_month)
                opening_month_number = date_month_number % max_month if date_month_number % max_month else max_month
            else:
                opening_month_number = 0

            # first week of period may be partial, depending on starting weekday
            period_start_weekday = active_periods[date].period.lower.isoweekday()
            # get number of requested week since start of active period
            date_week_number = int(((date-active_periods[date].period.lower).days + period_start_weekday - 1) / 7) + 1
            # get number of requested weekday in month, or since period start modulo repetition
            if max_month:
                # if max_month > 0, week numbers refer to weekdays from the start of month.
                # range is (1, 2, 3, 4) or (1, 2, 3, 4, 5) depending on how long the month is
                opening_week_number = int((date.day - 1) / 7) + 1 if max_week else 0
            else:
                # if max_month = 0, week numbers refer to weeks since period start
                if max_week:
                    # zero remainder is mapped to max_week (range is 1, 2,  ..., max_week)
                    opening_week_number = date_week_number % max_week if date_week_number % max_week else max_week
                else:
                    opening_week_number = 0
            openings[date] = active_periods[date].openings.filter(weekday=date.isoweekday(), week=opening_week_number, month=opening_month_number)
        return openings


class Keyword(BaseModel):
    targets = models.ManyToManyField(Target, related_name='keywords', db_index=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('Keyword')
        verbose_name_plural = _('Keywords')


class Period(BaseModel):
    target = models.ForeignKey(Target, on_delete=models.PROTECT, related_name='periods', db_index=True)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN, db_index=True)
    override = models.BooleanField(default=False, db_index=True)
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
    weekday = models.IntegerField(choices=Weekday.choices, db_index=True)
    status = models.IntegerField(choices=Status.choices, default=Status.OPEN, db_index=True)
    opens = models.TimeField(null=True, db_index=True)
    closes = models.TimeField(null=True, db_index=True)
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    # by default, all openings are for the first week of the rule, i.e. rotation of 1 week.
    week = models.IntegerField(verbose_name=_('Week number'), default=1, db_index=True)
    # by default, no monthly rotation. if month > 0,  week number refers to weeks within month.
    month = models.IntegerField(verbose_name=_('Month number'), default=0, db_index=True)

    def __str__(self):
        return f'{self.period}: {self.week},{self.month}: {Weekday(self.weekday).label} {Status(self.status).label} {self.opens}-{self.closes}'

    class Meta:
        verbose_name = _('Opening')
        verbose_name_plural = _('Openings')


class DailyHours(object):
    # This is not strictly a django model, but we adhere to the same methods? or simpler API may suffice
    # Store two years (current and future) in memory.
    start = pd.Timestamp.today().floor(freq = 'D') - pd.offsets.YearBegin()
    end = pd.Timestamp.today().floor(freq = 'D') + pd.offsets.YearEnd() + pd.DateOffset(years=1)
    columns = pd.date_range(start, end).date
    # this is the stored final structure, containing raw opening data
    hours = pd.DataFrame(columns=columns)

    def __init__(self, *args, **kwargs):
        start_time = time.process_time()
        targets = list(Target.objects.all().prefetch_related('periods__openings'))
        # Just a single query to get the whole db
        data = (target.get_openings_for_range(self.start.date(), self.end.date()) for target in targets)
        # this is the processing structure with references to django objects, used to generate the hours
        openings = pd.DataFrame(
            [*data],
            index=targets,
            columns=self.columns
            )

        print(time.process_time() - start_time)
        print('dataframe generated')
        print(openings.memory_usage())
        




        # 1. sort targets by max number of openings per day
        #grouped_openings = Opening.objects.all().values('id','period', 'weekday', 'week', 'month')
        #print(grouped_openings)
        #target_ids = Target.objects.all().values_list('id', flat=True)
        #print(target_ids)
        #grouped_targets = Target.objects.all().values('periods')
        ##print(grouped_targets)
        #annotated_targets = Target.objects.all().annotate(slots=Count('periods__openings'))
        #print(annotated_targets)
        #for target in annotated_targets:
        #    print(target)
            #print(target.periods.all())
            #for period in target.periods.all():
                #print(period.openings.all())
        #    print(target.slots)
        #print(self.start)
        #print(self.end)
        #print(self.columns)
        #print(self.dataframe)
        #print(self.dataframe.memory_usage())

        # pseudo-algorithm:
    # ================
    # 1. sort targets by max number of slots -- get number (test_targets())
    # 2. iterate days, iterate sorted targets (generate_table(test_targets()))
    # 3. insert values into array
    #
    # btw: array size = iterate slots, sum number of targets per slot, (multiply by days)
    #