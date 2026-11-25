import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.crops.services.scoring import _month_range_text, score_crop
from apps.crops.tests.test_services import make_crop

pytestmark = pytest.mark.django_db

FLAT = {"temp_c": [27.0] * 12, "rain_mm": [200.0] * 12, "years": 10, "source": "test"}
COLD = {"temp_c": [5.0] * 12, "rain_mm": [200.0] * 12, "years": 10, "source": "test"}


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
    temps[7] = 5.0  # August: the third month of a 3-month crop sown in June
    item = score_crop(make_crop(), "N", "tropical", 6, None, {**FLAT, "temp_c": temps})
    assert item["components"]["temperature"] == 47  # 0.7 * (2/3) + 0.3 * 0


def test_month_range_text():
    assert _month_range_text([11, 12, 1, 2]) == "Nov to Feb"
    assert _month_range_text([6]) == "Jun"
    assert _month_range_text([1, 2, 6, 7]) == "Jan to Feb, Jun to Jul"
    assert _month_range_text(range(1, 13)) == "year-round"
    assert _month_range_text([]) == ""


def test_recommend_api_uses_climate_averages_for_any_month(monkeypatch):
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
    assert quinoa["data"] == {"source": "demo", "verified": False}