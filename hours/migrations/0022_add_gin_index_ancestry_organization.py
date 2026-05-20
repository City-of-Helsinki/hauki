from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("hours", "0021_change_period_origin_unique_constraint"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="resource",
            index=GinIndex(
                fields=["ancestry_organization"],
                name="hours_res_anc_org_gin",
            ),
        ),
    ]
