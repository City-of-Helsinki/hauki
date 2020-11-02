from helusers.models import AbstractUser


class User(AbstractUser):
    def __str__(self):
        if self.first_name and self.last_name:
            return "%s %s (%s)" % (self.last_name, self.first_name, self.email)
        elif self.email:
            return self.email
        else:
            return self.username
