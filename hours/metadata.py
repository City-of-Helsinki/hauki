from django.conf import settings
from django.utils import translation
from rest_framework.fields import ChoiceField
from rest_framework.metadata import SimpleMetadata


class TranslatedChoiceNamesMetadata(SimpleMetadata):
    def get_field_info(self, field):
        field_info = super().get_field_info(field)

        if isinstance(field, ChoiceField) and hasattr(field, "enum"):
            choices = []
            for val in field.enum:
                choice = {"value": val.value, "display_name": {}}
                for lang_code, _lang_name in settings.LANGUAGES:
                    with translation.override(lang_code):
                        choice["display_name"][lang_code] = str(val.label)

                choices.append(choice)

            field_info["choices"] = choices

        return field_info
