from datetime import datetime
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse

from hauki.views import _check_database, _get_package_version


@pytest.fixture(autouse=True)
def clear_version_cache():
    _get_package_version.cache_clear()
    yield
    _get_package_version.cache_clear()


@pytest.fixture
def url():
    return reverse("readiness")


@pytest.mark.django_db
def test_check_database_ok():
    assert _check_database() == "ok"


def test_check_database_error_on_exception():
    with patch("hauki.views.connection") as mock_conn:
        mock_conn.cursor.side_effect = Exception("DB is down")
        assert _check_database() == "error"


def test_get_package_version_reads_from_pyproject_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_bytes(b'[project]\nversion = "3.2.1"\n')
    with override_settings(BASE_DIR=str(tmp_path)):
        assert _get_package_version() == "3.2.1"


def test_get_package_version_returns_unknown_when_file_is_missing(tmp_path):
    with override_settings(BASE_DIR=str(tmp_path)):
        assert _get_package_version() == "unknown"


def test_get_package_version_returns_unknown_when_version_key_absent(tmp_path):
    (tmp_path / "pyproject.toml").write_bytes(b"[project]\n")
    with override_settings(BASE_DIR=str(tmp_path)):
        assert _get_package_version() == "unknown"


@pytest.mark.django_db
def test_readiness_ok(client, url):
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert {
        "status",
        "database",
        "packageVersion",
        "sentryRelease",
        "buildTime",
    } == set(data)


@pytest.mark.django_db
def test_readiness_503_when_db_down(client, url):
    with patch("hauki.views._check_database", return_value="error"):
        response = client.get(url)

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["database"] == "error"


def test_readiness_method_not_allowed_for_non_get(client, url):
    assert client.post(url).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sentry_release, expected",
    [(None, ""), ("v1.2.3", "v1.2.3")],
)
def test_readiness_sentry_release(client, url, sentry_release, expected):
    with override_settings(SENTRY_RELEASE=sentry_release):
        response = client.get(url)

    assert response.json()["sentryRelease"] == expected


@pytest.mark.django_db
def test_readiness_build_time_is_isoformat(client, url):
    build_time = datetime(2025, 6, 15, 8, 30, 0)
    with override_settings(APP_BUILD_TIME=build_time):
        response = client.get(url)

    assert response.json()["buildTime"] == build_time.isoformat()


@pytest.mark.django_db
def test_readiness_build_time_is_null_when_unset(client, url):
    with override_settings(APP_BUILD_TIME=None):
        response = client.get(url)

    assert response.json()["buildTime"] is None
