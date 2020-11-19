import datetime
import urllib.parse

import pytest
from django.urls import reverse
from pytz import UTC

from hours.authentication import calculate_signature, join_params
from hours.models import SignedAuthEntry
from users.models import User


@pytest.mark.django_db
def test_get_auth_required_unauthenticated(api_client):
    url = reverse("auth_required_test-list")
    response = api_client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_get_auth_required_header_invalid_signature(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    authz_string = (
        "haukisigned"
        " username=test_user"
        "&created_at=2020-10-01T06%3A35%3A00.917Z"
        "&valid_until=2020-11-01T06%3A45%3A00.917Z"
        "&signature=invalid_signature"
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid signature"


@pytest.mark.django_db
def test_get_auth_required_header_invalid_created_at(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    data = {
        "username": "test_user",
        "created_at": "2030-01-01T10:10:10.000Z",
        "valid_until": "2030-01-01T10:20:10.000Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid created_at"


@pytest.mark.django_db
def test_get_auth_required_header_invalid_valid_until(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    data = {
        "username": "test_user",
        "created_at": "2020-01-01T10:10:10.000Z",
        "valid_until": "2000-01-01T10:20:10.000Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid valid_until"


@pytest.mark.django_db
def test_get_auth_required_header_authenticated(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": "test_user",
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"


@pytest.mark.django_db
def test_join_user_to_organization(
    settings, api_client, data_source_factory, organization_factory
):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    data_source = data_source_factory(id="test")
    org = organization_factory(data_source=data_source, origin_id=1234)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": "test_user",
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "organization": org.id,
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    user = User.objects.get(username="test_user")

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_existing_user(
    settings, api_client, user_factory, data_source_factory, organization_factory
):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    user = user_factory(username="test_user")

    data_source = data_source_factory(id="test")
    org = organization_factory(data_source=data_source, origin_id=1234)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": user.username,
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "organization": org.id,
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    assert User.objects.count() == 1

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_existing_user_and_organisation(
    settings, api_client, user_factory, data_source_factory, organization_factory
):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    user = user_factory(username="test_user")

    data_source = data_source_factory(id="test")
    org = organization_factory(data_source=data_source, origin_id=1234)

    user.organization_memberships.add(org)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": user.username,
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "organization": org.id,
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    assert User.objects.count() == 1

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_invalid_org(
    settings, api_client, data_source_factory, organization_factory
):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": "test_user",
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "organization": "test:2345",
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    user = User.objects.get(username="test_user")

    assert user.organization_memberships.count() == 0


@pytest.mark.django_db
def test_invalidate_signature_success_header_params(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    valid_until = now + datetime.timedelta(minutes=10)

    data = {
        "username": "test_user",
        "created_at": now.isoformat() + "Z",
        "valid_until": valid_until.isoformat() + "Z",
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    # Check that auth works
    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data == {"success": True}

    signed_auth_entry = SignedAuthEntry.objects.get(signature=signature)

    assert signed_auth_entry.created_at == now.replace(tzinfo=UTC)
    assert signed_auth_entry.valid_until == valid_until.replace(tzinfo=UTC)

    # Verify that the auth no longer works
    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalidate_signature_success_query_params(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"
    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "username": "test_user",
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    signature = calculate_signature(join_params(data))

    authz_string = "?" + urllib.parse.urlencode({**data, "signature": signature})

    # Check that auth works
    response = api_client.get(f"{url}{authz_string}")

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(f"{invalidate_url}{authz_string}")

    assert response.status_code == 200
    assert response.data == {"success": True}

    # Verify that the auth no longer works
    response = api_client.get(f"{url}{authz_string}")

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalidate_signature_no_params(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalidate_signature_invalid_params(settings, api_client):
    settings.HAUKI_SIGNED_AUTH_PSK = "testing"

    now = datetime.datetime.utcnow()

    data = {
        # username missing
        "created_at": now.isoformat() + "Z",
        "valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    signature = calculate_signature(join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "signature": signature}
    )

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
