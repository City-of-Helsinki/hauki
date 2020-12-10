from enumfields.drf import EnumField
from rest_framework.serializers import Serializer

from hours.enums import State
from hours.metadata import TranslatedChoiceNamesMetadata


def test_enum_translation_in_metadata(settings):
    class DummySerializer(Serializer):
        resource_state = EnumField(enum=State)

    metadata = TranslatedChoiceNamesMetadata()
    serializer = DummySerializer()

    serializer_metadata = metadata.get_serializer_info(serializer)

    resource_state_choices = serializer_metadata["resource_state"]["choices"]

    assert len(resource_state_choices) == len(State)

    for choice in resource_state_choices:
        assert set(choice["display_name"].keys()) == set(
            [k for k, n in settings.LANGUAGES]
        )
        assert all(choice["display_name"].values())
