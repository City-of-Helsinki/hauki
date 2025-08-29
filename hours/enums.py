from django.db.models import IntegerChoices, TextChoices
from django.utils.translation import pgettext_lazy as _


class State(TextChoices):
    OPEN = "open", _("State", "Open")
    CLOSED = "closed", _("State", "Closed")
    UNDEFINED = "undefined", _("State", "Undefined")
    SELF_SERVICE = "self_service", _("State", "Self service")
    WITH_KEY = "with_key", _("State", "With key")
    WITH_RESERVATION = "with_reservation", _("State", "With reservation")
    OPEN_AND_RESERVABLE = "open_and_reservable", _("State", "Open and reservable")
    WITH_KEY_AND_RESERVATION = (
        "with_key_and_reservation",
        _("State", "With key and reservation"),
    )
    ENTER_ONLY = "enter_only", _("State", "Enter only")
    EXIT_ONLY = "exit_only", _("State", "Exit only")
    WEATHER_PERMITTING = "weather_permitting", _("State", "Weather permitting")
    NOT_IN_USE = "not_in_use", _("State", "Not in use")
    MAINTENANCE = "maintenance", _("State", "Maintenance")
    RESERVED = "reserved", _("State", "Reserved")
    BY_APPOINTMENT = "by_appointment", _("State", "By appointment")
    NO_OPENING_HOURS = "no_opening_hours", _("State", "No opening hours")

    @classmethod
    def open_states(cls):
        return [
            cls.OPEN,
            cls.SELF_SERVICE,
            cls.WITH_KEY,
            cls.WITH_RESERVATION,
            cls.OPEN_AND_RESERVABLE,
            cls.WITH_KEY_AND_RESERVATION,
            cls.ENTER_ONLY,
            cls.WEATHER_PERMITTING,
            cls.RESERVED,
            cls.BY_APPOINTMENT,
        ]


class ResourceType(TextChoices):
    UNIT = "unit", _("ResourceType", "Unit")
    SUBSECTION = "section", _("ResourceType", "Section")
    SPECIAL_GROUP = "special_group", _("ResourceType", "Special group")
    CONTACT = "contact", _("ResourceType", "Contact email or phone number")
    ONLINE_SERVICE = "online_service", _("ResourceType", "Online service")
    SERVICE = "service", _("ResourceType", "Service")
    SERVICE_CHANNEL = "service_channel", _("ResourceType", "Service channel")
    SERVICE_AT_UNIT = "service_at_unit", _("ResourceType", "Service at unit")
    RESERVABLE = "reservable", _("ResourceType", "Reservable resource")
    BUILDING = "building", _("ResourceType", "Building")
    AREA = "area", _("ResourceType", "Area")
    ENTRANCE = "entrance_or_exit", _("ResourceType", "Entrance or exit")


class Weekday(IntegerChoices):
    MONDAY = 1, _("Weekday", "Monday")
    TUESDAY = 2, _("Weekday", "Tuesday")
    WEDNESDAY = 3, _("Weekday", "Wednesday")
    THURSDAY = 4, _("Weekday", "Thursday")
    FRIDAY = 5, _("Weekday", "Friday")
    SATURDAY = 6, _("Weekday", "Saturday")
    SUNDAY = 7, _("Weekday", "Sunday")

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


class RuleContext(TextChoices):
    PERIOD = "period", _("RuleContext", "Period")
    YEAR = "year", _("RuleContext", "Year")
    MONTH = "month", _("RuleContext", "Month")

    # Make strings used in the Rule.as_text method findable by makemessages
    _("every_rulecontext", "period")
    _("every_rulecontext", "year")
    _("every_rulecontext", "month")


class RuleSubject(TextChoices):
    DAY = "day", _("RuleSubject", "Day")
    WEEK = "week", _("RuleSubject", "Week")
    MONTH = "month", _("RuleSubject", "Month")
    MONDAY = "mon", _("RuleSubject", "Monday")
    TUESDAY = "tue", _("RuleSubject", "Tuesday")
    WEDNESDAY = "wed", _("RuleSubject", "Wednesday")
    THURSDAY = "thu", _("RuleSubject", "Thursday")
    FRIDAY = "fri", _("RuleSubject", "Friday")
    SATURDAY = "sat", _("RuleSubject", "Saturday")
    SUNDAY = "sun", _("RuleSubject", "Sunday")

    # Make strings used in the Rule.as_text method findable by makemessages
    _("starting_from_nth_rulesubject", "day")
    _("starting_from_nth_rulesubject", "week")
    _("starting_from_nth_rulesubject", "month")
    _("starting_from_nth_rulesubject", "mon")
    _("starting_from_nth_rulesubject", "tue")
    _("starting_from_nth_rulesubject", "wed")
    _("starting_from_nth_rulesubject", "thu")
    _("starting_from_nth_rulesubject", "fri")
    _("starting_from_nth_rulesubject", "sat")
    _("starting_from_nth_rulesubject", "sun")

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


class FrequencyModifier(TextChoices):
    EVEN = "even", _("FrequencyModifier", "Even")
    ODD = "odd", _("FrequencyModifier", "Odd")
