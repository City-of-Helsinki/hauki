import logging
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.test import override_settings
from django_orghierarchy.models import Organization
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from hours.authentication import HaukiSignedAuthentication
from hours.models import DataSource, Resource, SignedAuthKey

CONFIGURED_KEY = "local-e2e-signing-key"


def get_test_signing_key():
    return SignedAuthKey.objects.get(data_source_id="test").signing_key


@pytest.mark.django_db
@override_settings(E2E_SIGNED_AUTH_KEY="")
def test_creates_random_signing_key_when_not_configured():
    call_command("create_e2e_test_data")

    assert len(get_test_signing_key()) == 128


@pytest.mark.django_db
@override_settings(E2E_SIGNED_AUTH_KEY="")
def test_rerun_keeps_existing_data_and_random_key():
    call_command("create_e2e_test_data")
    first_key = get_test_signing_key()

    call_command("create_e2e_test_data")

    assert SignedAuthKey.objects.filter(data_source_id="test").count() == 1
    assert get_test_signing_key() == first_key
    assert Resource.objects.filter(name="E2E Test Resource").count() == 1


@pytest.mark.django_db
@override_settings(E2E_SIGNED_AUTH_KEY=CONFIGURED_KEY)
def test_configured_key_authenticates_the_e2e_test_user(hsa_params_factory):
    call_command("create_e2e_test_data")

    params = hsa_params_factory(
        username="cypress_test_user",
        data_source=DataSource.objects.get(id="test"),
        organization=Organization.objects.get(id="test:cypress"),
        resource="test:1",
        signed_auth_key=SimpleNamespace(signing_key=CONFIGURED_KEY),
    )
    request = APIView().initialize_request(APIRequestFactory().get("/", params))

    user, _ = HaukiSignedAuthentication().authenticate(request)

    assert user.username == "cypress_test_user"


@pytest.mark.django_db
def test_configured_key_replaces_previously_generated_key():
    with override_settings(E2E_SIGNED_AUTH_KEY=""):
        call_command("create_e2e_test_data")

    with override_settings(E2E_SIGNED_AUTH_KEY=CONFIGURED_KEY):
        call_command("create_e2e_test_data")

    assert get_test_signing_key() == CONFIGURED_KEY


@pytest.mark.django_db
@override_settings(E2E_SIGNED_AUTH_KEY=CONFIGURED_KEY)
def test_configured_key_is_not_logged(caplog):
    with caplog.at_level(logging.INFO, logger="create_e2e_test_data"):
        call_command("create_e2e_test_data")

    assert "E2E_SIGNED_AUTH_KEY" in caplog.text
    assert CONFIGURED_KEY not in caplog.text
