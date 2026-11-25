from datetime import timedelta

import pytest
import requests
from django.utils import timezone

from apps.crops.models import ClimateNormal
from apps.crops.services import climate
from apps.crops.services.climate import climate_payload, get_climate_normals

pytestmark = pytest.mark.django_db


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def yearly_payload():
    times, tmax, tmin, rain = [], [], [], []
    for year, bonus in ((2023, 0), (2024, 10)):
        for month in range(1, 13):
            times.append(f"{year}-{month:02d}-15")
            tmax.append(30.0)
            tmin.append(20.0)
            rain.append(month * 10 + bonus)
    return {"daily": {"time": times, "temperature_2m_max": tmax, "temperature_2m_min": tmin, "precipitation_sum": rain}}


def test_normals_are_computed_stored_and_reused(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return FakeResponse(yearly_payload())

    monkeypatch.setattr(climate.requests, "get", fake_get)
    first = get_climate_normals(12.97, 77.59)
    assert first["temp_c"] == [25.0] * 12
    assert first["rain_mm"][0] == 15.0 and first["rain_mm"][11] == 125.0  # average of the two years
    assert first["years"] == 2
    assert ClimateNormal.objects.count() == 1

    second = get_climate_normals(13.05, 77.55)  # same 0.25 degree cell: no new download
    assert second == first and len(calls) == 1


def test_failure_returns_none_or_the_old_copy(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(climate.requests, "get", boom)
    assert get_climate_normals(1.0, 1.0) is None

    ClimateNormal.objects.create(
        cell_lat=2.0, cell_lon=2.0, temp_c=[20.0] * 12, rain_mm=[50.0] * 12, years=10,
        source="old", fetched_at=timezone.now() - timedelta(days=800),
    )
    stale = get_climate_normals(2.0, 2.0)
    assert stale is not None and stale["source"] == "old"


def test_chart_payload_shape():
    normals = {"temp_c": [20.0] * 12, "rain_mm": [50.0] * 12, "years": 10, "source": "test"}
    payload = climate_payload(normals)
    assert len(payload["monthly"]) == 12
    assert payload["monthly"][0] == {"month": 1, "temp_c": 20.0, "rain_mm": 50.0}
    assert climate_payload(None) is None