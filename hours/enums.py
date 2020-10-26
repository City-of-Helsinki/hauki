from django.utils.translation import pgettext_lazy as _
from enumfields import Enum


class State(Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNDEFINED = "undefined"
    SELF_SERVICE = "self_service"
    WITH_KEY = "with_key"
    WITH_RESERVATION = "with_reservation"
    WITH_KEY_AND_RESERVATION = "with_key_and_reservation"
    ENTER_ONLY = "enter_only"
    EXIT_ONLY = "exit_only"

    class Labels:
        OPEN = _("State", "Open")
        CLOSED = _("State", "Closed")
        UNDEFINED = _("State", "Undefined")
        SELF_SERVICE = _("State", "Self service")
        WITH_KEY = _("State", "With key")
        WITH_RESERVATION = _("State", "With reservation")
        WITH_KEY_AND_RESERVATION = _("State", "With key and reservation")
        ENTER_ONLY = _("State", "Enter only")
        EXIT_ONLY = _("State", "Exit only")


class ResourceType(Enum):
    UNIT = "unit"
    UNIT_SERVICE = "unit_service"
    SPECIAL_GROUP = "special_group"
    PERSON = "person"
    TELEPHONE = "telephone"
    SERVICE = "service"
    SERVICE_CHANNEL = "service_channel"
    SERVICE_AT_UNIT = "service_at_unit"
    RESOURCE = "resource"
    BUILDING = "building"
    AREA = "area"

    class Labels:
        UNIT = _("ResourceType", "Unit")
        UNIT_SERVICE = _("ResourceType", "Unit service")
        SPECIAL_GROUP = _("ResourceType", "Special group")
        PERSON = _("ResourceType", "Person")
        TELEPHONE = _("ResourceType", "Telephone")
        SERVICE = _("ResourceType", "Service")
        SERVICE_CHANNEL = _("ResourceType", "Service channel")
        SERVICE_AT_UNIT = _("ResourceType", "Service at unit")
        RESOURCE = _("ResourceType", "Resource")
        BUILDING = _("ResourceType", "Building")
        AREA = _("ResourceType", "Area")


class Weekday(Enum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7

    class Labels:
        MONDAY = _("Weekday", "Monday")
        TUESDAY = _("Weekday", "Tuesday")
        WEDNESDAY = _("Weekday", "Wednesday")
        THURSDAY = _("Weekday", "Thursday")
        FRIDAY = _("Weekday", "Friday")
        SATURDAY = _("Weekday", "Saturday")
        SUNDAY = _("Weekday", "Sunday")

    @classmethod
    def business_days(cls):
        return [cls.MONDAY, cls.TUESDAY, cls.WEDNESDAY, cls.THURSDAY, cls.FRIDAY]

    @classmethod
    def weekend(cls):
        return [cls.SATURDAY, cls.SUNDAY]

    @classmethod
    def from_iso_weekday(cls, iso_weekday_num):
        for member in cls.__members__.values():
            if member.value == iso_weekday_num:
                return member


class RuleContext(Enum):
    PERIOD = "period"
    YEAR = "year"
    MONTH = "month"
    # WEEK = "week"

    class Labels:
        PERIOD = _("RuleContext", "Period")
        YEAR = _("RuleContext", "Year")
        MONTH = _("RuleContext", "Month")
        # WEEK = _("RuleContext", "Week")


class RuleSubject(Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    MONDAY = "mon"
    TUESDAY = "tue"
    WEDNESDAY = "wed"
    THURSDAY = "thu"
    FRIDAY = "fri"
    SATURDAY = "sat"
    SUNDAY = "sun"

    class Labels:
        DAY = _("RuleSubject", "Day")
        WEEK = _("RuleSubject", "Week")
        MONTH = _("RuleSubject", "Month")
        MONDAY = _("RuleSubject", "Monday")
        TUESDAY = _("RuleSubject", "Tuesday")
        WEDNESDAY = _("RuleSubject", "Wednesday")
        THURSDAY = _("RuleSubject", "Thursday")
        FRIDAY = _("RuleSubject", "Friday")
        SATURDAY = _("RuleSubject", "Saturday")
        SUNDAY = _("RuleSubject", "Sunday")

    def is_singular(self):
        return self in [
            self.DAY,
            self.MONDAY,
            self.TUESDAY,
            self.WEDNESDAY,
            self.THURSDAY,
            self.FRIDAY,
            self.SATURDAY,
            self.SUNDAY,
        ]

    @classmethod
    def weekday_subjects(cls):
        return [
            cls.MONDAY,
            cls.TUESDAY,
            cls.WEDNESDAY,
            cls.THURSDAY,
            cls.FRIDAY,
            cls.SATURDAY,
            cls.SUNDAY,
        ]

    def as_isoweekday(self):
        if self not in self.weekday_subjects():
            return None

        return self.weekday_subjects().index(self) + 1

    def as_weekday(self):
        if self not in self.weekday_subjects():
            return None

        return self.weekday_subjects().index(self)


class FrequencyModifier(Enum):
    EVEN = "even"
    ODD = "odd"

    class Labels:
        EVEN = _("FrequencyModifier", "Even")
        ODD = _("FrequencyModifier", "Odd")
