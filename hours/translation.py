import simple_history
from modeltranslation.translator import TranslationOptions, translator

from .models import DataSource, DatePeriod, Resource, Rule, TimeSpan


class DataSourceTranslationOptions(TranslationOptions):
    fields = ("name", "description")


class ResourceTranslationOptions(TranslationOptions):
    fields = ("name", "description", "address")


class DatePeriodTranslationOptions(TranslationOptions):
    fields = ("name", "description")


class TimeSpanTranslationOptions(TranslationOptions):
    fields = ("name", "description")


class RuleTranslationOptions(TranslationOptions):
    fields = ("name", "description")


translator.register(DataSource, DataSourceTranslationOptions)
translator.register(Resource, ResourceTranslationOptions)
translator.register(DatePeriod, DatePeriodTranslationOptions)
translator.register(TimeSpan, TimeSpanTranslationOptions)
translator.register(Rule, RuleTranslationOptions)


# class HaukiHistoricalRecords(HistoricalRecords):
#     def post_save(self, instance, created, using=None, **kwargs):
#         if not created and hasattr(instance, "skip_history_when_saving"):
#             return
#
#         if not kwargs.get("raw", False):
#             if created:
#                 history_type = "+"
#             else:
#                 history_type = "~"
#
#                 if isinstance(instance, SafeDeleteModel):
#                     pass
#
#             self.create_historical_record(instance, history_type, using=using)


simple_history.register(DataSource)
simple_history.register(Resource)
simple_history.register(DatePeriod)
simple_history.register(TimeSpan)
simple_history.register(Rule)
