from django.core.management.base import BaseCommand

from hours.models import Resource


class Command(BaseCommand):
    help = "Update child resource ancestry fields"

    def handle(self, *args, **options):
        child_resources = Resource.objects.filter(parents__isnull=False).distinct()

        for child_resource in child_resources:
            self.stdout.write(
                "\nChild #{} {}".format(child_resource.id, child_resource)
            )
            child_resource.update_ancestry(update_child_ancestry_fields=False)
