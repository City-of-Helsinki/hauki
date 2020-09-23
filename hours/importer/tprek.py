from django import db

from ..models import Target, DataSource, TargetType
from django_orghierarchy.models import Organization
from .base import Importer, register_importer
from .sync import ModelSyncher


@register_importer
class TPRekImporter(Importer):
    name = "tprek"

    def setup(self):
        self.URL_BASE = 'http://www.hel.fi/palvelukarttaws/rest/v4/'
        ds_args = dict(id='tprek')
        defaults = dict(name='Toimipisterekisteri')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

    def get_unit_identifiers(self, unit_id: str, data: dict) -> list:
        """
        Takes target id and unit data dict in TPREK v4 API format and returns the corresponding serialized
        TargetIdentifier data
        """
        identifiers = []
        if 'sources' in data:
            for source in data["sources"]:
                identifier = {
                    'target_id': unit_id,
                    'data_source_id': source['source'],
                    'origin_id': source['id']
                }
                identifiers.append(identifier)
        return identifiers

    def get_unit_data(self, data: dict) -> dict:
        """
        Takes unit data dict in TPREK v4 API format and returns the corresponding serialized Target data.
        """
        obj_id = 'tprek:%s' % str(data['id'])
        obj_organization, created = Organization.objects.get_or_create(data_source=self.data_source,
                                                                       origin_id=data['dept_id'])
        if created:
            self.logger.debug('Created missing organization tprek:%s' % data['dept_id'])
        unit_data = {
            'id': obj_id,
            'data_source': self.data_source,
            'origin_id': str(data['id']),
            'name': self.clean_text(data['name_fi']),
            'description': self.clean_text(data.get('desc_fi', "")),
            'address': self.clean_text(data.get('street_address_fi', "") + ', ' + data.get('address_city_fi', "")),
            'same_as': self.get_url('unit', data['id']),
            'organization': obj_organization,
            'identifiers': self.get_unit_identifiers(obj_id, data)
        }
        return unit_data

    @db.transaction.atomic
    def import_units(self):
        queryset = Target.objects.filter(data_source=self.data_source, target_type=TargetType.UNIT)
        if self.options.get('single', None):
            obj_id = self.options['single']
            obj_list = [self.api_get('unit', obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            self.logger.info("Loading TPREK units...")
            obj_list = self.api_get('unit')
            self.logger.info("%s units loaded" % len(obj_list))
        syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=self.mark_deleted,
                               check_deleted_func=self.check_deleted)
        for idx, data in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                self.logger.info("%s units processed" % idx)
            unit_data = self.get_unit_data(data)
            unit = self.save_target(unit_data)
            syncher.mark(unit)

        syncher.finish()

    @db.transaction.atomic
    def import_connections(self):
        # TODO: connections as targets
        pass

    def import_targets(self):
        self.import_units()
        self.import_connections()
