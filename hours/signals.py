from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from hours.models import Resource


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
