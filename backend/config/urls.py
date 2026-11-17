from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    checks = {}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        cache.set("health:ping", "1", 5)
        checks["cache"] = "ok" if cache.get("health:ping") == "1" else "error"
    except Exception:
        checks["cache"] = "error"
    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", **checks},
        status=200 if healthy else 503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/scans/", include("apps.scans.urls")),
    path("api/crops/", include("apps.crops.urls")),
]