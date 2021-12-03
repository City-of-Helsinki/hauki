from django.core.management.base import BaseCommand
from django.db import transaction

from hours.models import Resource


class Command(BaseCommand):
    help = (
        "Update denormalized opening hours fields (date_periods_hash and "
        "date_periods_as_text) in resources"
    )

    def add_arguments(self, parser):
        parser.add_argument("resource_ids", nargs="*", type=int)

    def handle(self, *args, **options):
        if options["resource_ids"]:
            resources = Resource.objects.filter(id__in=options["resource_ids"])
        else:
            resources = Resource.objects.all()

        resources = resources.prefetch_related(
            "date_periods",
            "date_periods__time_span_groups",
            "date_periods__time_span_groups__time_spans",
            "date_periods__time_span_groups__rules",
        )

        with transaction.atomic():
            for resource in resources:
                self.stdout.write("Resource #{} {}".format(resource.id, resource))
                resource.update_denormalized_date_periods_data()
