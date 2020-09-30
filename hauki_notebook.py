#%% [markdown]

# # Hauki notebook

# This notebook will create very simple opening hours if not present in the db.

#%%

# Django settings require some extra
import os

os.chdir("/Users/riku/Dropbox/Tyo/hauki")

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "hauki.settings"
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgis:///hauki"

# IPython runs async, which does not allow safe access to ORM
# Do NOT run this concurrently with other threads accessing ORM
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# settings.configure()
import django
from django.conf import settings

django.setup()

# %%
from rich import print as rprint
from rich.console import Console

console = Console()

# %%
from hours.models import DailyHours, DataSource, Opening, Period, Target, Weekday
from hours.tests.conftest import (
    long_period,
    openings,
    period_first_week_opening,
    period_second_week_closing,
)

# %%
ds, created = DataSource.objects.get_or_create(id="hauki")
ds.save()
target, created = Target.objects.get_or_create(data_source=ds, origin_id="1")
target.save()
period = long_period(ds)(target, "1")
period.save()
opening = period_first_week_opening(ds)(period, Weekday.MONDAY)
opening.save()
closing = period_second_week_closing(ds)(period, Weekday.MONDAY)
closing.save()

# %%

# Daily hours should now be populated
rprint(DailyHours.objects.all())

# %%
