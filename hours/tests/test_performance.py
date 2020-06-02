import time
import datetime
import pytest
from hours.models import Target


@pytest.mark.django_db
def test_daily_hours_update_and_get(periods, openings):
    print(periods)
    print('periods and openings set up')
    start_time = time.process_time()
    # we could only iterate per target, as we created all the periods at the same time
    # however, in practice periods are always created one by one, not in bulk, and update is done for each period.
    # however, each update considers *all* the periods, no change after the first update 
    for period in periods:
        period.update_daily_hours()
    print('daily hours updated')
    print(time.process_time() - start_time)
    assert (time.process_time() - start_time < 15)
    start_time = time.process_time()
    for target in Target.objects.all():
        print(target.daily_hours.filter(date__range=(datetime.date(2021,7,1), datetime.date(2021,7,31))).select_related('opening').query)
        print(target.daily_hours.filter(date__range=(datetime.date(2021,7,1), datetime.date(2021,7,31))).select_related('opening'))
    print('All daily hours printed for July')
    print(time.process_time() - start_time)
    assert (time.process_time() - start_time < 0.05)