from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from hours.models import DatePeriod, Resource, Rule, TimeSpan, TimeSpanGroup


@receiver(m2m_changed, sender=Resource.children.through)
def resource_children_changed(sender, **kwargs):
    if kwargs.get("action") not in ("post_add", "post_remove"):
        return

    # Prevent accidental loop
    if kwargs.get("pk_set") and kwargs["instance"].id in kwargs["pk_set"]:
        return

    # This is a result of a child.parents.add(parent) (or remove) call.
    # Update ancestry on the child
    if kwargs["reverse"]:
        kwargs["instance"].update_ancestry()
        return

    # Otherwise the child/children are added or removed in the parent
    # Fetch the children and update ancestry on them.
    for child in Resource.objects.filter(id__in=kwargs["pk_set"]):
        child.update_ancestry()


_RESOURCES_TO_BE_CLEARED = {}


@receiver(m2m_changed, sender=Resource.children.through)
def resource_children_cleared(sender, **kwargs):
    if kwargs.get("action") not in ("pre_clear", "post_clear"):
        return

    #
    # Handle pre_clear
    #
    # Resources to be removed must be saved before post_clear because
    # the children are not available anymore then.
    if kwargs.get("action") == "pre_clear":
        if kwargs["reverse"]:
            # No need to save because this is a result of a child.parents.clear() call
            # and therefore the instance is the child.
            return

        _RESOURCES_TO_BE_CLEARED[kwargs["instance"]] = list(
            kwargs["instance"].children.all()
        )
        return

    #
    # Handle post_clear
    #
    # This is a result of a child.parents.add(parent) (or remove) call.
    # Update ancestry on the child
    if kwargs["reverse"]:
        kwargs["instance"].update_ancestry()
        return

    # Otherwise the child/children are cleared in the parent
    # Go through the saved children and update ancestry on them.
    if kwargs["instance"] in _RESOURCES_TO_BE_CLEARED:
        for child in _RESOURCES_TO_BE_CLEARED[kwargs["instance"]]:
            child.update_ancestry()

        del _RESOURCES_TO_BE_CLEARED[kwargs["instance"]]


@receiver(post_save, sender=Resource)
def post_create_resource(sender, instance, created, **kwargs):
    if not created:
        return

    instance.update_denormalized_date_periods_data()


OPENING_HOURS_MODELS = {
    DatePeriod: lambda i: i.resource,
    TimeSpanGroup: lambda i: i.period.resource,
    TimeSpan: lambda i: i.group.period.resource,
    Rule: lambda i: i.group.period.resource,
}


def post_save_opening_hours(sender, instance, **kwargs):
    if sender not in OPENING_HOURS_MODELS.keys():
        return

    resource = OPENING_HOURS_MODELS[sender](instance)

    if not resource:
        return

    resource.update_denormalized_date_periods_data()


def connect_opening_hours_post_save_receivers():
    for model in OPENING_HOURS_MODELS:
        post_save.connect(receiver=post_save_opening_hours, sender=model)


def disconnect_opening_hours_post_save_receivers():
    for model in OPENING_HOURS_MODELS:
        post_save.disconnect(receiver=post_save_opening_hours, sender=model)


class DeferUpdatingDenormalizedDatePeriodData:
    def __init__(self):
        self.affected_resources = set()
        self.handler = None

    def get_handler(self):
        if not self.handler:

            def track_affected_resources(sender, instance, **kwargs):
                if sender not in OPENING_HOURS_MODELS.keys():
                    return

                resource = OPENING_HOURS_MODELS[sender](instance)
                if resource:
                    self.affected_resources.add(resource)

            self.handler = track_affected_resources

        return self.handler

    def __enter__(self):
        disconnect_opening_hours_post_save_receivers()

        for model in OPENING_HOURS_MODELS:
            post_save.connect(receiver=self.get_handler(), sender=model)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for model in OPENING_HOURS_MODELS:
            post_save.disconnect(receiver=self.get_handler(), sender=model)

        for resource in self.affected_resources:
            resource.update_denormalized_date_periods_data()

        connect_opening_hours_post_save_receivers()


connect_opening_hours_post_save_receivers()
