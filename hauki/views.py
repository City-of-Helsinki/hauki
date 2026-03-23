import functools
import tomllib
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@functools.cache
def _get_package_version() -> str:
    try:
        pyproject_path = Path(settings.BASE_DIR) / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


def _check_database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception:
        return "error"


@require_GET
def readiness(request):
    db_status = _check_database()
    readiness_status = "ok" if db_status == "ok" else "error"
    build_time = getattr(settings, "APP_BUILD_TIME", None)

    return JsonResponse(
        {
            "status": readiness_status,
            "packageVersion": _get_package_version(),
            "release": settings.SENTRY_RELEASE or "",
            "buildTime": build_time.isoformat() if build_time else None,
            "database": db_status,
        },
        status=200 if readiness_status == "ok" else 503,
    )
