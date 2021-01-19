import logging

# Per module logger
logger = logging.getLogger(__name__)


class ModelSyncher(object):
    def __init__(
        self,
        queryset,
        delete_func=None,
        check_deleted_func=None,
        allow_deleting_func=None,
    ):
        d = {}
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
            raise Exception("Object %s already marked" % obj)
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
                f"a total of {len(self.obj_dict)} items"
            )
        for obj in delete_list:
            if self.allow_deleting_func:
                if not self.allow_deleting_func(obj):
                    raise Exception(
                        "Deleting %s not allowed by the importer" % str(obj)
                    )
            if self.delete_func:
                self.delete_func(obj)
                deleted = True
            else:
                obj.delete()
                deleted = True
            if deleted:
                logger.info("Deleting object %s" % obj)
