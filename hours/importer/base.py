import base64
import logging
import os
import re
import struct
import time
import functools

from django.conf import settings
from django import db


from hours.models import Target

class Importer(object):
    def __init__(self, options):
        self.logger = logging.getLogger("%s_importer" % self.name)
        self.options = options
        self.setup()

    @staticmethod
    def mark_deleted(obj):
        return obj.soft_delete()

    @staticmethod
    def check_deleted(obj):
        return obj.deleted

    @staticmethod
    def clean_text(text, strip_newlines=False):
        # remove non-breaking spaces and separators
        text = text.replace('\xa0', ' ').replace('\x1f', '')
        # remove nil bytes
        text = text.replace(u'\u0000', ' ')
        if strip_newlines:
            text = text.replace('\r', '').replace('\n', ' ')
        # remove consecutive whitespaces
        return re.sub(r'\s\s+', ' ', text, re.U).strip()

    def _set_field(self, obj, field_name, val):
        if not hasattr(obj, field_name):
            self.logger.debug("'%s' not there!" % field_name)
            self.logger.debug(vars(obj))

        obj_val = getattr(obj, field_name)
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

    def _update_fields(self, obj, info, skip_fields):
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

    @db.transaction.atomic
    def save_target(self, data):
        args = dict(data_source=data['data_source'], origin_id=data['origin_id'])
        obj_id = "%s:%s" % (data['data_source'].id, data['origin_id'])
        try:
            obj = Target.objects.get(**args)
            obj._created = False
        except Target.DoesNotExist:
            obj = Target(**args)
            obj._created = True
            obj.id = obj_id
            obj.save()
            self.logger.debug("%s created" % obj)
        obj._changed = False
        obj._changed_fields = []

        skip_fields = ['id', 'data_source', 'origin_id']
        self._update_fields(obj, data, skip_fields)
        self._set_field(obj, 'deleted', False)
        self._set_field(obj, 'published', True)

        # identifiers = {x.namespace: x for x in obj.identifiers.all()}
        # for id_data in data.get('identifiers', []):
        #     ns = id_data['namespace']
        #     val = id_data['value']
        #     if ns in identifiers:
        #         id_obj = identifiers[ns]
        #         if id_obj.value != val:
        #             id_obj.value = val
        #             id_obj.save()
        #             obj._changed = True
        #     else:
        #         id_obj = UnitIdentifier(unit=obj, namespace=ns, value=val)
        #         id_obj.save()
        #         obj._changed = True

        if obj._changed:
            if not obj._created:
                self.logger.debug("%s changed: %s" % (obj, ', '.join(obj._changed_fields)))
            obj.save()

        return obj

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
