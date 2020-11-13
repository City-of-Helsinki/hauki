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
        users_organizations = set()
        users_organizations.update(self.admin_organizations.all())
        users_organizations.update(self.organization_memberships.all())

        return users_organizations
