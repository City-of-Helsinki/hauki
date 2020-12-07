from django.core.management.base import BaseCommand

from hours.models import Resource


class Command(BaseCommand):
    help = "Update child resource ancestry fields"

    def add_arguments(self, parser):
        parser.add_argument("resource_ids", nargs="+", type=int)

    def handle(self, *args, **options):
        if options["resource_ids"]:
            child_resources = Resource.objects.filter(id__in=options["resource_ids"])
        else:
            child_resources = Resource.objects.filter(parents__isnull=False).distinct()

        for child_resource in child_resources:
            self.stdout.write(
                "\nChild #{} {}".format(child_resource.id, child_resource)
            )
            child_resource.update_ancestry(update_child_ancestry_fields=False)
