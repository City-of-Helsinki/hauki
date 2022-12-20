import datetime
import urllib.parse

import pytest
from django.urls import reverse
from pytz import UTC
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from hours.authentication import (
    HaukiSignedAuthentication,
    calculate_signature,
    join_params,
)
from hours.models import SignedAuthEntry
from users.models import User


@pytest.mark.django_db
def test_get_auth_required_unauthenticated(api_client):
    url = reverse("auth_required_test-list")
    response = api_client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_get_auth_required_header_invalid_signature(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    authz_string = (
        "haukisigned"
        " hsa_source=" + data_source.id + "&hsa_username=test_user"
        "&hsa_created_at=2020-10-01T06%3A35%3A00.917Z"
        "&hsa_valid_until=2020-11-01T06%3A45%3A00.917Z"
        "&hsa_signature=invalid_signature"
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_signature"


@pytest.mark.django_db
def test_get_auth_required_header_invalid_created_at(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": "2030-01-01T10:10:10.000Z",
        "hsa_valid_until": "2030-01-01T10:20:10.000Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_created_at"


@pytest.mark.django_db
def test_get_auth_required_header_timezone_missing_created_at(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat(),
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat()
        + "-04:00",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_created_at"


@pytest.mark.django_db
def test_get_auth_required_header_invalid_valid_until(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": "2020-01-01T10:10:10.000Z",
        "hsa_valid_until": "2000-01-01T10:20:10.000Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_valid_until"


@pytest.mark.django_db
def test_get_auth_required_header_timezone_missing_valid_until(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat(),
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_valid_until"


@pytest.mark.django_db
def test_get_auth_required_header_timezone_missing_created_at_and_valid_until(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat(),
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat(),
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_created_at"


@pytest.mark.django_db
def test_get_auth_required_header_authenticated(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"


@pytest.mark.django_db
def test_join_user_to_organization(
    api_client, data_source_factory, signed_auth_key_factory, organization_factory
):
    data_source = data_source_factory(id="test")
    signed_auth_key = signed_auth_key_factory(data_source=data_source)
    org = organization_factory(data_source=data_source, origin_id=1234)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "hsa_organization": org.id,
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    user = User.objects.get(username="test_user")

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_existing_user(
    api_client,
    user_factory,
    user_origin_factory,
    data_source_factory,
    signed_auth_key_factory,
    organization_factory,
):
    data_source = data_source_factory(id="test")
    user = user_factory(username="test_user")
    user_origin_factory(user=user, data_source=data_source)

    signed_auth_key = signed_auth_key_factory(data_source=data_source)
    org = organization_factory(data_source=data_source, origin_id=1234)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": user.username,
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "hsa_organization": org.id,
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    assert User.objects.count() == 1

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_existing_user_and_organisation(
    api_client,
    user_factory,
    user_origin_factory,
    data_source_factory,
    signed_auth_key_factory,
    organization_factory,
):
    data_source = data_source_factory(id="test")
    user = user_factory(username="test_user")
    user_origin_factory(user=user, data_source=data_source)

    signed_auth_key = signed_auth_key_factory(data_source=data_source)
    org = organization_factory(data_source=data_source, origin_id=1234)

    user.organization_memberships.add(org)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": user.username,
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "hsa_organization": org.id,
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    assert User.objects.count() == 1

    assert user.organization_memberships.count() == 1


@pytest.mark.django_db
def test_join_user_to_organization_invalid_org(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
        "hsa_organization": "test:2345",
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    user = User.objects.get(username="test_user")

    assert user.organization_memberships.count() == 0


@pytest.mark.django_db
def test_signed_auth_entry_not_invalidated(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()
    valid_until = now + datetime.timedelta(minutes=10)

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": valid_until.isoformat() + "Z",
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    # Check that auth works
    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"

    # Add a non invalidated entry to the database
    SignedAuthEntry.objects.create(
        signature=signature,
        created_at=now.replace(tzinfo=UTC),
        valid_until=valid_until.replace(tzinfo=UTC),
    )

    # Check that auth still works
    response = api_client.get(url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 200
    assert response.data["username"] == "test_user"


@pytest.mark.django_db
def test_invalidate_signature_success_header_params(
    api_client, data_source, signed_auth_key_factory
):
    url = reverse("auth_required_test-list")

    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    now = datetime.datetime.utcnow()

    valid_until = now + datetime.timedelta(minutes=10)

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": valid_until.isoformat() + "Z",
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
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
def test_invalidate_signature_success_query_params(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    url = reverse("auth_required_test-list")

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "?" + urllib.parse.urlencode({**data, "hsa_signature": signature})

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
def test_invalidate_signature_no_params(api_client):

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalidate_signature_invalid_params(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        # hsa_username missing
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalidate_signature_missing_timezone(
    api_client, data_source, signed_auth_key_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat(),
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat(),
    }

    signature = calculate_signature(signed_auth_key.signing_key, join_params(data))

    authz_string = "haukisigned " + urllib.parse.urlencode(
        {**data, "hsa_signature": signature}
    )

    # Invalidate the signature
    invalidate_url = reverse("invalidate_hauki_auth_signature")
    response = api_client.post(invalidate_url, HTTP_AUTHORIZATION=authz_string)

    assert response.status_code == 403
    assert str(response.data["detail"]) == "Invalid hsa_created_at"


@pytest.mark.django_db
def test_authenticate_new_user(api_client, data_source, signed_auth_key_factory):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": "test_user",
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    params = {**data, "hsa_signature": signature}

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    authenticated_user = auth.authenticate(request)[0]

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"


@pytest.mark.django_db
def test_authenticate_existing_user_no_existing_data_source(
    api_client, data_source, signed_auth_key_factory, user_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    user = user_factory()

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": user.username,
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    params = {**data, "hsa_signature": signature}

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert auth.user_origin.user == user
    assert auth.user_origin.data_source == data_source


@pytest.mark.django_db
def test_authenticate_existing_user_existing_same_data_source(
    api_client, data_source, signed_auth_key_factory, user_factory, user_origin_factory
):
    signed_auth_key = signed_auth_key_factory(data_source=data_source)

    user = user_factory()
    user_origin_factory(user=user, data_source=data_source)

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source.id,
        "hsa_username": user.username,
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    params = {**data, "hsa_signature": signature}

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    authenticated_user = auth.authenticate(request)[0]

    assert authenticated_user.id == user.id
    assert authenticated_user.username == user.username


@pytest.mark.django_db
def test_authenticate_existing_user_existing_different_data_source(
    api_client,
    data_source_factory,
    signed_auth_key_factory,
    user_factory,
    user_origin_factory,
):
    data_source1 = data_source_factory()
    data_source2 = data_source_factory()

    signed_auth_key = signed_auth_key_factory(data_source=data_source1)

    user = user_factory()
    user_origin_factory(user=user, data_source=data_source2)

    now = datetime.datetime.utcnow()

    data = {
        "hsa_source": data_source1.id,
        "hsa_username": user.username,
        "hsa_created_at": now.isoformat() + "Z",
        "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
    }

    source_string = join_params(data)
    signature = calculate_signature(signed_auth_key.signing_key, source_string)

    params = {**data, "hsa_signature": signature}

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert auth.user_origin.user == user
    assert auth.user_origin.data_source == data_source1


@pytest.mark.django_db
def test_auth_data_no_org_or_resource(api_client, data_source, hsa_params_factory):
    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization is None
    assert auth.resource is None


@pytest.mark.django_db
def test_auth_data_org(
    api_client, data_source, organization_factory, hsa_params_factory
):
    org = organization_factory(data_source=data_source, origin_id=1234)

    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
        "organization": org,
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization == org
    assert auth.resource is None


@pytest.mark.django_db
def test_auth_data_resource(
    api_client,
    data_source,
    resource_factory,
    resource_origin_factory,
    hsa_params_factory,
):
    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)

    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
        "resource": resource,
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization is None
    assert auth.resource == resource


@pytest.mark.django_db
def test_auth_data_resource_data_source_id(
    api_client,
    data_source,
    resource_factory,
    resource_origin_factory,
    hsa_params_factory,
):
    resource = resource_factory()
    resource_origin = resource_origin_factory(
        resource=resource, data_source=data_source, origin_id="12345"
    )

    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
        "resource": "{}:{}".format(
            resource_origin.data_source.id, resource_origin.origin_id
        ),
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization is None
    assert auth.resource == resource


@pytest.mark.django_db
def test_auth_data_resource_different_data_source(
    api_client,
    data_source_factory,
    resource_factory,
    resource_origin_factory,
    hsa_params_factory,
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source2)

    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
        "resource": resource,
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization is None
    assert auth.resource is None


@pytest.mark.django_db
def test_auth_data_child_resource(
    api_client,
    data_source,
    resource_factory,
    resource_origin_factory,
    hsa_params_factory,
):
    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory()
    resource2.parents.add(resource)

    hsa_params = {
        "username": "test_user",
        "data_source": data_source,
        "resource": resource2,
    }
    params = hsa_params_factory(**hsa_params)

    # Create a fake DRF request
    request_factory = APIRequestFactory()
    http_request = request_factory.get("/", params)
    request = APIView().initialize_request(http_request)

    auth = HaukiSignedAuthentication()
    (authenticated_user, auth) = auth.authenticate(request)

    assert authenticated_user.id is not None
    assert authenticated_user.username == "test_user"

    assert auth.user == authenticated_user
    assert auth.user_origin.data_source == data_source
    assert auth.has_organization_rights is False
    assert auth.organization is None
    assert auth.resource == resource2
