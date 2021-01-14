from django.utils import timezone
from pytz import InvalidTimeError, utc
from rest_framework.fields import DateTimeField


class TimezoneRetainingDateTimeField(DateTimeField):
    def enforce_timezone(self, value):
        field_timezone = getattr(self, "timezone", self.default_timezone())

        if field_timezone is not None:
            if timezone.is_aware(value):
                return value
            try:
                return timezone.make_aware(value, field_timezone)
            except InvalidTimeError:
                self.fail("make_aware", timezone=field_timezone)
        elif (field_timezone is None) and timezone.is_aware(value):
            return timezone.make_naive(value, utc)
        return value
