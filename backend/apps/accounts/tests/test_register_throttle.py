import pytest
from rest_framework.test import APIClient

from apps.accounts.throttles import RegisterRateThrottle

pytestmark = pytest.mark.django_db


def test_register_is_throttled_per_ip():
    api = APIClient()
    limit = int(RegisterRateThrottle.THROTTLE_RATES["register"].split("/")[0])

    for i in range(limit):
        r = api.post(
            "/api/auth/register/",
            {"username": f"grower{i}", "email": f"grower{i}@example.com", "password": "Str0ng-Passw0rd!x"},
            format="json",
        )
        assert r.status_code == 201

    r = api.post(
        "/api/auth/register/",
        {"username": "grower_extra", "email": "extra@example.com", "password": "Str0ng-Passw0rd!x"},
        format="json",
    )
    assert r.status_code == 429
    assert r.data["code"] == "rate_limited"
    assert r.data["retry_after_seconds"] > 0
    assert "Retry-After" in r