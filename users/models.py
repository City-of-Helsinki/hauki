from helusers.models import AbstractUser


class User(AbstractUser):
    def __str__(self):
        if self.first_name and self.last_name:
            return "%s %s (%s)" % (self.last_name, self.first_name, self.email)
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
