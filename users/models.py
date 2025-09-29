from django.db import models
from django.utils.translation import gettext_lazy as _
from helusers.models import AbstractUser


class User(AbstractUser):
    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.last_name} {self.first_name} ({self.email})"
        elif self.email:
            return self.email
        else:
            return self.username

    def get_all_organizations(self) -> set:
        # returns admin and member organizations and their descendants
        if (
            not self.admin_organizations.all()
            and not self.organization_memberships.all()
        ):
            return set()
        # regular users have rights to all organizations below their level
        orgs = set()
        for org in self.admin_organizations.all():
            if org not in orgs:
                orgs.update(org.get_descendants(include_self=True))
        for org in self.organization_memberships.all():
            if org not in orgs:
                orgs.update(org.get_descendants(include_self=True))
        # for multiple orgs, we have to combine the querysets
        return orgs


class UserOrigin(models.Model):
    user = models.ForeignKey(User, related_name="origins", on_delete=models.CASCADE)
    data_source = models.ForeignKey("hours.DataSource", on_delete=models.CASCADE)
    origin_id = models.CharField(
        verbose_name=_("Origin ID"), max_length=100, null=True, blank=True
    )

    class Meta:
        verbose_name = _("User origin")
        verbose_name_plural = _("User origins")
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "origin_id"],
                name="unique_user_origin_identifier_per_data_source",
            ),
            models.UniqueConstraint(
                fields=["data_source", "user"],
                name="unique_user_per_data_source",
            ),
        ]

    def __str__(self):
        return f"UserOrigin {self.data_source}:{self.origin_id}"
