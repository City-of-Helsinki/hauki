# Generated by Django 4.2.13 on 2024-08-13 10:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_userorigin"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="userorigin",
            constraint=models.UniqueConstraint(
                fields=("data_source", "user"), name="unique_user_per_data_source"
            ),
        ),
    ]
