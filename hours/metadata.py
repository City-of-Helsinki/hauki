from django.conf import settings
from django.utils import translation
from django.utils.encoding import force_str
from rest_framework.fields import ChoiceField
from rest_framework.metadata import SimpleMetadata


class TranslatedChoiceNamesMetadata(SimpleMetadata):
    def get_field_info(self, field):
        field_info = super().get_field_info(field)

        if isinstance(field, ChoiceField) and hasattr(field, "choices"):
            translated_choices = []
            for value, label in field.choices.items():
                choice = {"value": value, "display_name": {}}
                for lang_code, _lang_name in settings.LANGUAGES:
                    with translation.override(lang_code):
                        choice["display_name"][lang_code] = force_str(label)

                translated_choices.append(choice)

            field_info["choices"] = translated_choices

        return field_info
