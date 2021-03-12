from django import db

from ..models import DataSource, DatePeriod, Resource, ResourceOrigin
from .base import Importer, register_importer
from .sync import ModelSyncher


@register_importer
class HaukiImporter(Importer):
    """
    This barebones importer imports and syncs all opening hours data from an instance
    of Hauki backend for all the resources in the db that have a Hauki origin_id.
    """

    name = "hauki"

    def setup(self):
        self.URL_BASE = "https://hauki-test.oc.hel.ninja/v1/"
        ds_args = dict(id="hauki")
        defaults = dict(name="Hauki")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )

    def get_hours_from_api(self, resources: list) -> dict:
        """
        Fetch opening hours for listed resources from the Hauki api.
        """
        hauki_ids = [
            origin.origin_id
            for origin in ResourceOrigin.objects.filter(
                data_source=self.data_source, resource__in=resources
            )
        ]

        params = {
            "resource": ",".join(hauki_ids),
        }
        data = self.api_get("date_period", None, params)

        if len(data):
            return data

        return {}

    @db.transaction.atomic
    def import_openings(self):
        resources = Resource.objects.filter(origins__data_source=self.data_source)
        if self.options.get("single", None):
            resources = resources.filter(origins__origin_id=self.options["single"])
        self.logger.info("{} Hauki resources found".format(resources.count()))

        queryset = DatePeriod.objects.filter(resource__in=resources).prefetch_related(
            "time_span_groups__time_spans"
        )
        syncher = ModelSyncher(
            queryset,
            data_source=self.data_source,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )
        hauki_data = self.get_hours_from_api(resources)
        for period_datum in hauki_data:
            # replace inline data_source objects with data_source_ids
            for idx, origin in enumerate(period_datum["origins"]):
                period_datum["origins"][idx] = {
                    "data_source_id": origin["data_source"]["id"],
                    "origin_id": origin["origin_id"],
                }
            # add original hauki id
            period_datum["origins"].append(
                {"data_source_id": self.data_source.id, "origin_id": period_datum["id"]}
            )
            # find resource in local db
            period_datum["resource"] = resources.get(
                origins__origin_id=period_datum["id"]
            )
            del period_datum["id"]
            period = self.save_dateperiod(period_datum)
            syncher.mark(period)
        syncher.finish()
