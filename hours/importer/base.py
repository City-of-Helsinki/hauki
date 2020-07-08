import base64
import logging
import os
import re
import struct
import time
import functools
import requests

from django.conf import settings
from django import db


from hours.models import BaseModel, Target, TargetIdentifier, DataSource, Period, Opening

class Importer(object):
    def __init__(self, options):
        self.logger = logging.getLogger("%s_importer" % self.name)
        self.options = options
        self.setup()

    def get_url(self, resource_name: str, res_id: str=None) -> str:
        url = "%s%s/" % (self.URL_BASE, resource_name)
        if res_id is not None:
            url = "%s%s/" % (url, res_id)
        return url

    def api_get(self, resource_name: str, res_id: str=None, params: dict=None) -> dict:
        url = self.get_url(resource_name, res_id)
        self.logger.info("Fetching URL %s with params %s " % (url, params))
        resp = requests.get(url, params)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def mark_deleted(obj: BaseModel) -> bool:
        return obj.soft_delete()

    @staticmethod
    def check_deleted(obj: BaseModel) -> bool:
        return obj.deleted

    @staticmethod
    def clean_text(text:str, strip_newlines: bool=False) -> str:
        # remove non-breaking spaces and separators
        text = text.replace('\xa0', ' ').replace('\x1f', '')
        # remove nil bytes
        text = text.replace(u'\u0000', ' ')
        if strip_newlines:
            text = text.replace('\r', '').replace('\n', ' ')
        # remove consecutive whitespaces
        return re.sub(r'\s\s+', ' ', text, re.U).strip()

    def _set_field(self, obj: BaseModel, field_name: str, val: object):
        """
        Sets the field_name field of obj to val, if changed.
        """
        if not hasattr(obj, field_name):
            self.logger.debug("'%s' not there!" % field_name)
            self.logger.debug(vars(obj))

        obj_val = getattr(obj, field_name, None)
        if obj_val == val:
            return

        field = obj._meta.get_field(field_name)
        if getattr(field, 'max_length', None) and val is not None:
            if len(val) > field.max_length:
                raise Exception("field '%s' too long (max. %d): %s" % field_name, field.max_length, val)

        setattr(obj, field_name, val)
        obj._changed = True
        if not hasattr(obj, '_changed_fields'):
            obj._changed_fields = []
        obj._changed_fields.append(field_name)

    def _update_fields(self, obj: BaseModel, info: dict, skip_fields: list):
        """
        Updates the fields in obj according to info.
        """
        obj_fields = list(obj._meta.fields)
        # trans_fields = translator.get_options_for_model(type(obj)).fields
        # for field_name, lang_fields in trans_fields.items():
        #     lang_fields = list(lang_fields)
        #     for lf in lang_fields:
        #         lang = lf.language
        #         # Do not process this field later
        #         skip_fields.append(lf.name)

        #         if field_name not in info:
        #             continue

        #         data = info[field_name]
        #         if data is not None and lang in data:
        #             val = data[lang]
        #         else:
        #             val = None
        #         self._set_field(obj, lf.name, val)

        #     # Remove original translated field
        #     skip_fields.append(field_name)

        for d in skip_fields:
            for f in obj_fields:
                if f.name == d:
                    obj_fields.remove(f)
                    break

        for field in obj_fields:
            field_name = field.name
            if field_name not in info:
                continue
            self._set_field(obj, field_name, info[field_name])

    def _update_or_create_object(self, klass: type, data: dict) -> BaseModel:
        """
        Takes the class and serialized data, creates and/or updates the BaseModel object and returns it unsaved
        for class-specific processing and saving.
        """
        args = dict(data_source=data['data_source'], origin_id=data['origin_id'])
        obj_id = "%s:%s" % (data['data_source'].id, data['origin_id'])
        try:
            obj = klass.objects.get(**args)
            obj._created = False
        except klass.DoesNotExist:
            obj = klass(**args)
            obj._created = True
            obj.id = obj_id
        obj._changed = False
        obj._changed_fields = []

        skip_fields = ['id', 'data_source', 'origin_id']
        self._update_fields(obj, data, skip_fields)
        self._set_field(obj, 'deleted', False)
        self._set_field(obj, 'published', True)
        return obj

    @db.transaction.atomic
    def save_target(self, data: dict) -> Target:
        """
        Takes the serialized target data, creates and/or updates the corresponding Target object, saves and returns it.
        """
        obj = self._update_or_create_object(Target, data)
        if obj._created:
            obj.save()
            self.logger.debug("%s created" % obj)

        # Update related identifiers after the target has been created
        identifiers = {x.data_source_id: x for x in obj.identifiers.all()}
        for identifier in data.get('identifiers', []):
            data_source_id = identifier['data_source_id']
            origin_id = identifier['origin_id']
            if data_source_id in identifiers:
                existing_identifier = identifiers[data_source_id]
                if existing_identifier.origin_id != origin_id:
                    existing_identifier.origin_id = origin_id
                    existing_identifier.save()
                    obj._changed = True
                    obj._changed_fields.append('identifiers')
            else:
                data_source, created = DataSource.objects.get_or_create(id=data_source_id)
                if created:
                    self.logger.debug('Created missing data source %s' % data_source_id)
                new_identifier = TargetIdentifier(target=obj, data_source=data_source, origin_id=origin_id)
                new_identifier.save()
                obj._changed = True
                obj._changed_fields.append('identifiers')

        if obj._changed:
            if not obj._created:
                self.logger.debug("%s changed: %s" % (obj, ', '.join(obj._changed_fields)))
            obj.save()

        return obj

    @db.transaction.atomic
    def save_period(self, data: dict) -> Period:
        """
        Takes the serialized Period data with Openings, creates and/or updates the corresponding Period object,
        saves and returns it.
        """
        obj = self._update_or_create_object(Period, data)
        if obj._created:
            obj.save()
            self.logger.debug("%s created" % obj)

        # Update openings after the period has been created
        openings = obj.openings.all()
        openings.delete()
        new_openings = []
        for opening in data.get('openings', []):
            # openings have no identifiers in kirkanta and they are generated from data
            # therefore, we cannot identify existing openings with new ones
            new_opening = Opening(period=obj,
                                  weekday=opening['weekday'],
                                  week=opening['week'],
                                  status=opening['status'],
                                  description=opening.get('description', None),
                                  opens=opening.get('opens', None),
                                  closes=opening.get('closes', None)
                                  )
            new_openings.append(new_opening)
        Opening.objects.bulk_create(new_openings)
        obj._changed = True
        obj._changed_fields.append('openings')
        if not obj._created:
            self.logger.debug("%s changed: %s" % (obj, ', '.join(obj._changed_fields)))

        # Saving updates the daily hours for the duration of the period
        obj.save()

importers = {}

def register_importer(klass):
    importers[klass.name] = klass
    return klass


def get_importers():
    if importers:
        return importers
    module_path = __name__.rpartition('.')[0]
    # Importing the packages will cause their register_importer() methods
    # being called.
    for fname in os.listdir(os.path.dirname(__file__)):
        module, ext = os.path.splitext(fname)
        if ext.lower() != '.py':
            continue
        if module in ('__init__', 'base'):
            continue
        full_path = "%s.%s" % (module_path, module)
        ret = __import__(full_path, locals(), globals())
    return importers
