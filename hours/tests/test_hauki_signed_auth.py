import datetime
import urllib.parse

import pytest
from django.urls import reverse

from hours.authentication import calculate_signature, join_params


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
