from hours.models import Target, DataSource, TargetIdentifier, TargetType, Period, Opening, DailyHours, Status

KIRKANTA_STATUS_MAP = {
    0: Status.CLOSED,
    1: Status.OPEN,
    2: Status.SELF_SERVICE
}

def check_opening_hours(data):
    # Check that all library hours from data are found in db
    kirkanta_id = data['id']
    target = Target.objects.get(identifiers__data_source='kirkanta', identifiers__origin_id=kirkanta_id)
    if not data['schedules']:
        print('No opening hours found for library %s' % target)
        return
    print('Checking hours for library %s' % target)

    # TODO: Fix the checks below not to use pytest or asserts, so it can run in production
    # This way the check is faster and we check that the hours are identical (no extra hours)
    # start = data['schedules'][0]['date']
    # end = data['schedules'][-1]['date']
    # daily_hours = groupby(list(DailyHours.objects.filter(
    #     date__gte=start, date__lte=end, target=target
    #     ).select_related('opening').order_by(
    #         'date','opening__opens','opening__closes','opening__status'
    #         )), key=lambda x: x.date)
    # for day_in_data, day_in_db in zip_longest(data['schedules'], daily_hours, fillvalue=None):
    #     if day_in_data == None:
    #         raise Exception('Missing day in incoming data')
    #     if day_in_db == None:
    #         raise Exception('Missing hours in database')
    #     if type(day_in_data['date']) != date:
    #         day_in_data['date'] = parse_date(day_in_data['date'])
    #     assert day_in_data['date'] == day_in_db[0]
    #     times_in_data = sorted(day_in_data['times'], key=itemgetter('from', 'to', 'status'))
    #     if not times_in_data:
    #         hours_in_db = next(day_in_db[1])
    #         with pytest.raises(StopIteration):
    #             next(day_in_db[1])
    #         assert Status.CLOSED == hours_in_db.opening.status
    #         assert str(day_in_data['period']) == hours_in_db.opening.period.origin_id
    #     for hours_in_data, hours_in_db in zip_longest(times_in_data, day_in_db[1], fillvalue=None):
    #         if hours_in_data == None:
    #             raise Exception('Extra hours in database')
    #         if hours_in_db == None:
    #             raise Exception('Missing hours in database')
    #         assert parse_time(hours_in_data['from']) == hours_in_db.opening.opens
    #         assert parse_time(hours_in_data['to']) == hours_in_db.opening.closes
    #         assert KIRKANTA_STATUS_MAP[hours_in_data['status']] == hours_in_db.opening.status
    #         assert str(day_in_data['period']) == hours_in_db.opening.period.origin_id

    for day in data['schedules']:
        if day['times']:
            for opening in day['times']:
                daily_hours = DailyHours.objects.get(date=day['date'],
                                                     target=target,
                                                     opening__opens=opening['from'],
                                                     opening__closes=opening['to'],
                                                     opening__status=KIRKANTA_STATUS_MAP[opening['status']],
                                                     opening__period__origin_id=day['period'])
        else:
            daily_hours = DailyHours.objects.get(date=day['date'],
                                                 target=target,
                                                 opening__status=Status.CLOSED,
                                                 opening__period__origin_id=day['period'])