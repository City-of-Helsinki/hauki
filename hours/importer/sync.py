import logging

# Per module logger
logger = logging.getLogger(__name__)


class ModelSyncher:
    def __init__(
        self,
        queryset,
        data_source=None,
        delete_func=None,
        check_deleted_func=None,
        allow_deleting_func=None,
    ):
        d = {}
        self.data_source = data_source
        self.delete_func = delete_func
        self.check_deleted_func = check_deleted_func
        self.allow_deleting_func = allow_deleting_func

        # here we assume the queryset is distinct. otherwise this will fail
        for obj in queryset:
            # we need a dict to access all objects, luckily model instances are hashable
            d[obj] = obj
            # this only resets the initial queryset, objects outside it may still have
            # _found or _changed True
            obj._found = False
            obj._changed = False

        self.obj_dict = d

    def mark(self, obj):
        if getattr(obj, "_found", False):
            raise Exception(f"Object {obj} already marked")
        if obj not in self.obj_dict:
            self.obj_dict[obj] = obj
        else:
            obj = self.obj_dict[obj]
        obj._found = True

    def finish(self, force=False):
        delete_list = []
        for obj in self.obj_dict:
            if obj._found:
                # We have to reset _found so we don't mark or match the same object
                # across several synchers.
                # Only relevant if consecutive synchers get different querysets;
                # then the marked object might come from outside the initial syncher
                # queryset.
                # That results in spurious _found values in both found and non-found
                # objects.
                obj._found = False
                obj._changed = False
                klass = type(obj)
                if getattr(obj, "_created", False) and hasattr(klass, "origins"):
                    # double-check that created object origins are still in db at
                    # the end of import!
                    origin_field = klass.origins.field
                    origin_query = {
                        "data_source": self.data_source,
                        origin_field.name: obj,
                    }
                    try:
                        origin_field.model.objects.get(**origin_query)
                    except origin_field.model.DoesNotExist:
                        raise AssertionError(
                            f"Somebody has changed the origin of {obj} to"
                            " point to another object while it was being"
                            " created. This most likely means multiple"
                            " imports are being run at the same time. Please"
                            " don't do that. It may result in imported"
                            " data being duplicated. Aborting import and"
                            " rolling back transaction."
                        )
                    except origin_field.model.MultipleObjectsReturned:
                        pass

                continue
            if self.check_deleted_func is not None and self.check_deleted_func(obj):
                continue
            delete_list.append(obj)
        if (
            len(delete_list) > 5
            and len(delete_list) > len(self.obj_dict) * 0.2
            and not force
        ):
            raise Exception(
                f"Attempting to delete {len(delete_list)} out of "
                f"a queryset of {len(self.obj_dict)} filtered items of "
                f"type {type(obj)}. This may indicate that the "
                f"data in the original source has changed suddenly. "
                f"If you are sure you want to delete over 20 % of "
                f"the selected queryset, please run the importer with the "
                f"--force parameter."
            )
        for obj in delete_list:
            if self.allow_deleting_func:
                if not self.allow_deleting_func(obj):
                    raise Exception(f"Deleting {str(obj)} not allowed by the importer")
            if self.delete_func:
                self.delete_func(obj)
                deleted = True
            else:
                obj.delete()
                deleted = True
            if deleted:
                logger.info(f"Deleting object {obj}")
