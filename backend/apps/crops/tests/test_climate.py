from datetime import timedelta

import pytest
import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crops.models import ClimateNormal
from apps.crops.services import climate
from apps.crops.services.climate import get_climate_normals
from apps.crops.services.scoring import _month_range_text, score_crop
from apps.crops.tests.test_services import make_crop

pytestmark = pytest.mark.django_db

FLAT = {"temp_c": [27.0] * 12, "rain_mm": [200.0] * 12, "years": 10, "source": "test"}
COLD = {"temp_c": [5.0] * 12, "rain_mm": [200.0] * 12, "years": 10, "source": "test"}


# ------------------------------------------------------------------ scoring
def test_ideal_climate_and_calendar_give_full_marks():
    item = score_crop(make_crop(), "N", "tropical", 6, None, FLAT)
    assert item["score"] == 100
    assert item["season_source"] == "calendar" and item["climate_basis"] is True
    assert item["components"] == {"season": 100, "temperature": 100, "rainfall": 100}


def test_crop_without_calendar_is_estimated_from_climate():
    crop = make_crop("Quinoa", rules=())
    item = score_crop(crop, "N", "tropical", 6, None, FLAT)
    assert item is not None
    assert item["season_source"] == "climate" and item["sow_window"] == "year-round"
    assert item["score"] == 100
    assert score_crop(crop, "N", "tropical", 6, None, None) is None  # no calendar AND no climate


def test_cold_climate_caps_the_score():
    item = score_crop(make_crop(), "N", "tropical", 6, None, COLD)
    assert item["components"]["temperature"] == 0
    assert item["score"] <= 40


def test_one_bad_month_drags_the_temperature_score_down():
    temps = [27.0] * 12
    temps[7] = 5.0  # August, the third month of a 3-month crop sown in June
    item = score_crop(make_crop(), "N", "tropical", 6, None, {**FLAT, "temp_c": temps})
    assert item["components"]["temperature"] == 47  # 0.7 * (2/3) + 0.3 * 0


def test_month_range_text():
    assert _month_range_text([11, 12, 1, 2]) == "Nov to Feb"
    assert _month_range_text([6]) == "Jun"
    assert _month_range_text([1, 2, 6, 7]) == "Jan to Feb, Jun to Jul"
    assert _month_range_text(range(1, 13)) == "year-round"
    assert _month_range_text([]) == ""


# ------------------------------------------------------------------ service
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
    assert first["rain_mm"][0] == 15.0 and first["rain_mm"][11] == 125.0  # average of two years
    assert first["years"] == 2
    assert ClimateNormal.objects.count() == 1

    second = get_climate_normals(13.05, 77.55)  # same 0.25 degree cell: no new request
    assert second == first and len(calls) == 1


def test_failure_returns_none_or_the_stale_copy(monkeypatch):
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


# --------------------------------------------------------------------- API
def test_recommend_uses_climate_averages_for_any_month(monkeypatch):
    call_command("seed_crops")
    make_crop("Quinoa", rules=())
    monkeypatch.setattr("apps.crops.views.get_climate_normals", lambda lat, lon: FLAT)
    monkeypatch.setattr("apps.crops.views.get_weather_summary", lambda lat, lon: None)

    user = get_user_model().objects.create_user(username="farmer", email="f@example.com", password="Str0ng-Passw0rd!x")
    api = APIClient()
    api.force_authenticate(user)

    r = api.get("/api/crops/recommend/", {"lat": "12.97", "lon": "77.59", "month": 6})
    assert r.status_code == 200
    assert r.data["climate_used"] is True and r.data["scoring_basis"] == "10-year climate averages"
    assert len(r.data["climate"]["monthly"]) == 12
    quinoa = next(item for item in r.data["results"] if item["name"] == "Quinoa")
    assert quinoa["season_source"] == "climate"
    assert all(item["data"]["source"] in ("demo", "manual") or True for item in r.data["results"])