from django.apps import AppConfig


class HoursConfig(AppConfig):
    name = "hours"

    def ready(self):
        import hours.signals  # NOQA: F401 'hours.signals' imported but unused
