import logging
from itertools import groupby
from operator import itemgetter
from collections import OrderedDict
from datetime import date, datetime
from psycopg2.extras import DateRange
import pandas as pd
import numpy as np
import delorean
import holidays

from django import db
from django.conf import settings

from ..models import Target, TargetIdentifier, DataSource, Period, Status, Weekday
from .base import Importer, register_importer
from .sync import ModelSyncher

KIRKANTA_STATUS_MAP = {
    0: Status.CLOSED,
    1: Status.OPEN,
    2: Status.SELF_SERVICE
}
fi_holidays = holidays.Finland()

@register_importer
class KirjastotImporter(Importer):
    name = "kirjastot"

    def setup(self):
        self.URL_BASE = 'https://api.kirjastot.fi/v4/'
        ds_args = dict(id='kirkanta')
        defaults = dict(name='kirjastot.fi')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

    @staticmethod
    def parse_date(date: str) -> date:
        date = datetime.strptime(date, '%Y-%m-%d').date()
        return date

    @staticmethod
    def get_date_range(start: date=None, back: int = 1, forward: int = 12) -> (date, date):
        """
        Returns a date range of "back" months before and "forward" months after given date, or today.
        """
        base = delorean.Delorean(start)
        begin = base.last_month(back).date.replace(day=1)
        end = base.next_month(forward).date.replace(day=1)
        return begin, end
            
    def get_hours_from_api(self, target: Target, start: date, end: date) -> dict:
        """
        Fetch opening hours for Target from kirjastot.fi's v4 API for the given date range.
        """

        kirkanta_id = target.identifiers.get(data_source=self.data_source).origin_id
        print(kirkanta_id)

        params = {
            "with": "schedules",
            "period.start": start,
            "period.end": end
        }
        data = self.api_get('library', kirkanta_id, params)
        if data["total"] > 0:
            return data["data"]
        return False

    def check_period_common_dates_equal(self, period_id: int, first_data: list, second_data: list) -> bool:
        """
        Checks that existing openings in both lists are equal, if their period_ids match.
        """
        if not first_data or not second_data:
            return True
        for first_opening, second_opening in zip(first_data, second_data):
            if not first_opening or not second_opening:
                # either pattern has no data for the given day, so it's always a match for the day
                continue
            # times are not necessarily in the same order. order the times with status and start first
            first_opening['times'].sort(key=itemgetter('status', 'from', 'to'))
            second_opening['times'].sort(key=itemgetter('status', 'from', 'to'))
            if (first_opening['period'] == period_id and
                second_opening['period'] == period_id and
                first_opening['times'] != second_opening['times']):
                return False
        return True

    def get_weekday_pattern_candidate(self, weekday_openings_by_date: list, n: int, period_id: int) -> list:
        """
        Returns the pattern for n consecutive weeks from weekday_openings_by_date,
        merging data from several repetitions to find all n weeks with period_id.
        """
        first_n_weeks =  weekday_openings_by_date[0:n]
        weeks_to_return = []
        for index, weekly_opening in enumerate(first_n_weeks):
            try:
                round = 0
                while weekly_opening['period'] != period_id:
                    # this opening won't do, looking at the next repetition
                    round += 1
                    weekly_opening = weekday_openings_by_date[round*n+index]
            except IndexError:
                # period doesn't contain a single opening for this weekday
                weekly_opening = None
            weeks_to_return.append(weekly_opening)
        return weeks_to_return

    def get_openings(self, data: list) -> list:
        """
        Generates serialized opening rules for a single period from sorted list of dates and their opening times.
        The period is defined by the first date in the data. Each period needs to be processed separately,
        starting from the period starting date.
        """
        period_id = data[0]['period']
        # starting date is needed to identify the first week, in case of repetitions of multiple weeks
        start_date = data[0]['date']
        start_weekday = start_date.isoweekday()
        openings_by_weekday = groupby(sorted(data, key=itemgetter('weekday')), key=itemgetter('weekday'))

        # 1st (preprocess): group by differing times for the same weekday, if found, and find the repetitions
        repetition_pattern = {}
        for weekday, openings_by_date in openings_by_weekday:
            openings_by_date=list(openings_by_date)
            n_weeks = len(openings_by_date)
            pattern_candidate = []
            # starting from the assumption that the openings repeat weekly, we increase the repetition by
            # one week and try again until the pattern matches
            for repetition in range(1, n_weeks+1):
                pattern_candidate = self.get_weekday_pattern_candidate(openings_by_date, repetition, period_id)
                slices = [openings_by_date[i:i+repetition] for i in range(0, n_weeks, repetition)]
                # *all* slices must be equal whenever the period_id matches
                for pattern_slice in slices:
                    if not self.check_period_common_dates_equal(period_id, pattern_slice, pattern_candidate):
                        # slice mismatch, no repetition
                        break
                else:
                    # end of loop reached, hooray! We have the repetition
                    break
            repetition_pattern[weekday] = pattern_candidate
        # if there, by any chance, should be competing pattern lengths for different weekdays, the resulting
        # total rule must have length that is the least common multiple of all the lengths
        repetition_lengths = [len(repetition) for repetition in repetition_pattern.values()]
        max_week = np.lcm.reduce(repetition_lengths)
        if max_week > 1:
            self.logger.debug("Detected repetition of %s weeks in period %s" % (max_week, period_id))

        # 2nd (loop again): generate the openings based on the data for each weekday and week in repetition
        opening_data = []
        for week in range(1, max_week+1):
            for weekday in Weekday:
                # not all weekdays are present for short holiday periods
                if repetition_pattern.get(weekday):
                    # first week may be partial, so the 1st week openings are split between 1st and n+1th in the list
                    if week == 1 and weekday < start_weekday:
                        week_index = max_week-1
                    else:
                        week_index = week-1
                    # all patterns are not as long as the longest one. They repeat from the start earlier
                    repetition_length = len(repetition_pattern[weekday])
                    opening_times = repetition_pattern[weekday][week_index % repetition_length]
                    if not opening_times:
                        # Opening times may be empty if we have no data for this particular day of the period
                        continue
                    description = opening_times['info']
                    if not description:
                        # Use the holiday name if present
                        description = fi_holidays.get(opening_times['date'])
                    if opening_times['times']:
                        for time in opening_times['times']:
                            opening_data.append({
                                'weekday': weekday,
                                'week': week,
                                'status': KIRKANTA_STATUS_MAP[time['status']],
                                'description': opening_times['info'],
                                'opens': time['from'],
                                'closes': time['to']
                            })
                    else:
                        opening_data.append({
                            'weekday': weekday,
                            'week': week,
                            'status': Status.CLOSED,
                            'description': opening_times['info']
                        })
        return opening_data

    def get_periods(self, target: Target, data: dict) -> list:
        """
        Returns serialized period objects found in library data for the given target library.
        """
        # sort the data just in case the API didn't
        data['schedules'].sort(key=lambda x: x['date'])
        # parse and annotate the data with indices and weekdays
        for index, day in enumerate(data['schedules']):
            day['date'] = self.parse_date(day['date'])
            day['weekday'] = day['date'].isoweekday()
            day['index'] = index
        days_by_period = groupby(sorted(data['schedules'], key=itemgetter('period')), key=itemgetter('period'))
        periods = []
        for period_id, days in days_by_period:
            days = list(days)
            start = days[0]['date']
            start_index = days[0]['index']
            end = days[-1]['date']
            end_index = days[-1]['index']
            openings = self.get_openings(data['schedules'][start_index:end_index+1])
            if start == end:
                # name single day periods after the day
                name = days[0]['info']
            else:
                name = ''
            period_data = {
                'data_source': self.data_source,
                'origin_id': str(period_id),
                'target': target,
                'period': DateRange(lower=start, upper=end, bounds='[]'),
                'name': name,
                'openings': openings
            }
            periods.append(period_data)
        return periods

    @db.transaction.atomic
    def import_openings(self):
        libraries = Target.objects.filter(identifiers__data_source=self.data_source)
        if self.options.get('single', None):
            obj_id = self.options['single']
            libraries = libraries.filter(id=obj_id)
        print('%s libraries found' % libraries.count())
        begin, end = self.get_date_range()
        for library in libraries:
            data = self.get_hours_from_api(library, begin, end)
            if data:
                try:
                    periods = self.get_periods(library, data)
                    for period_data in periods:
                        period = self.save_period(period_data)
                    # TODO: synching for existing periods!
                except Exception as e:
                    import traceback
                    print("Problem in processing data of library ", library, traceback.format_exc())
            else:
                print("Could not find opening hours for library ", library)




        # queryset = Target.objects.filter(data_source=self.data_source, target_type=TargetType.UNIT)
        # if self.options.get('single', None):
        #     obj_id = self.options['single']
        #     obj_list = [self.api_get('unit', obj_id)]
        #     queryset = queryset.filter(id=obj_id)
        # else:
        #     self.logger.info("Loading TPREK units...")
        #     obj_list = self.api_get('unit')
        #     self.logger.info("%s units loaded" % len(obj_list))
        # syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=self.mark_deleted,
        #                        check_deleted_func=self.check_deleted)
        # for idx, data in enumerate(obj_list):
        #     if idx and (idx % 1000) == 0:
        #         self.logger.info("%s units processed" % idx)
        #     unit_data = self.get_unit_data(data)
        #     unit = self.save_target(unit_data)
        #     syncher.mark(unit)

        #syncher.finish()
        
# import datetime
# import delorean
# import requests
# from django.conf import settings
# from django.db import transaction
# from sentry_sdk import capture_message
# from resources.models import Unit
# from typing import Dict, List
# from .base import Importer, register_importer

# IMPORTER_NAME = "kirjastot"



# def parse_schedule(day_schedule: Dict[str, any]) -> Dict[str, any]:
#     date = datetime.datetime.strptime(day_schedule.get('date'), '%Y-%m-%d').date()
#     closed = day_schedule.get('closed', False)
#     info = day_schedule.get('info', '')
#     # only normal staffed opening hours synced for now.
#     # support for staffless and during day closed hours to be added.
#     staffed_opening_hours = [hours for hours in day_schedule.get('times', []) if hours['status'] == STAFFED_HOURS]
#     return {
#         'date': date,
#         'weekday': date.weekday(),
#         'closed': closed,
#         'info': info,
#         'staffed_opening_hours': staffed_opening_hours,
#     }


# def merge_opening_hours(opening_hours: List) -> Dict[str, datetime.time]:
#     """ A workaround helper that combines a list of opening times to a single
#     pair with the earliest opening and the latest closing time. """
#     opening_times = [parse_time(times['from']) for times in opening_hours]
#     closing_times = [parse_time(times['to']) for times in opening_hours]
#     return {
#         'from': min(opening_times) if opening_times else None,
#         'to': max(closing_times) if closing_times else None,
#     }


# def parse_time(time: str) -> datetime.time:
#     hour, minute = [int(num) for num in time.split(':')]
#     return datetime.time(hour=hour, minute=minute)


