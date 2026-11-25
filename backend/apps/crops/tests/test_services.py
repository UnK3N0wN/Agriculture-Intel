import pytest
import requests
from django.utils.text import slugify

from apps.crops.models import Crop, SeasonalRule
from apps.crops.services import weather
from apps.crops.services.region import classify_location
from apps.crops.services.scoring import rank_crops, score_crop
from apps.crops.services.season import get_season

IDEAL = {"avg_temp_c": 28, "avg_monthly_rain_mm": 200}


def make_crop(name="Rice", rules=(("N", "tropical", "Kharif", 6, 7),), **overrides):
    data = dict(
        name=name, slug=slugify(name), category="cereal", water_need="high",
        growing_days_min=90, growing_days_max=150,
        temp_min_c=18, temp_opt_min_c=22, temp_opt_max_c=32, temp_max_c=38,
        rain_min_mm=100, rain_max_mm=300,
    )
    data.update(overrides)
    crop = Crop.objects.create(**data)
    for hemi, zone, label, start, end in rules:
        SeasonalRule.objects.create(
            crop=crop, hemisphere=hemi, climate_zone=zone, season_label=label,
            sow_start_month=start, sow_end_month=end,
        )
    return Crop.objects.prefetch_related("seasonal_rules").get(pk=crop.pk)


# ------------------------------------------------------------------- region
@pytest.mark.parametrize(
    "lat, hemisphere, zone",
    [(12.97, "N", "tropical"), (28.6, "N", "subtropical"), (51.5, "N", "temperate"),
     (59.9, "N", "cold"), (-1.3, "S", "tropical"), (-33.9, "S", "subtropical")],
)
def test_classify_location(lat, hemisphere, zone):
    info = classify_location(lat, 0)
    assert (info.hemisphere, info.climate_zone) == (hemisphere, zone)


def test_region_label_is_readable():
    assert classify_location(12.97, 77.59).region == "Northern tropics"


# ------------------------------------------------------------------- season
def test_seasons_flip_between_hemispheres():
    assert get_season("N", "temperate", 1)["key"] == "winter"
    assert get_season("S", "temperate", 1)["key"] == "summer"
    assert get_season("N", "tropical", 7)["key"] == "wet"
    assert get_season("S", "tropical", 1)["key"] == "wet"


# ------------------------------------------------------------------ scoring
@pytest.mark.django_db
def test_perfect_conditions_score_100():
    item = score_crop(make_crop(), "N", "tropical", 6, IDEAL)
    assert item["score"] == 100 and item["label"] == "excellent"
    assert item["components"] == {"season": 100, "temperature": 100, "rainfall": 100}


@pytest.mark.django_db
def test_out_of_season_is_capped_at_poor():
    item = score_crop(make_crop(), "N", "tropical", 1, IDEAL)
    assert item["score"] <= 35 and item["label"] == "poor"


@pytest.mark.django_db
def test_one_month_before_window_is_half_season_credit():
    item = score_crop(make_crop(), "N", "tropical", 5, IDEAL)
    assert item["components"]["season"] == 50 and item["score"] == 75


@pytest.mark.django_db
def test_window_wrapping_the_year_end():
    crop = make_crop("Mustard", rules=(("N", "subtropical", "Winter", 11, 2),))
    assert score_crop(crop, "N", "subtropical", 1, IDEAL)["components"]["season"] == 100
    assert score_crop(crop, "N", "subtropical", 12, IDEAL)["components"]["season"] == 100


@pytest.mark.django_db
def test_temperature_outside_tolerance_is_capped():
    item = score_crop(make_crop(), "N", "tropical", 6, {"avg_temp_c": 10, "avg_monthly_rain_mm": 200})
    assert item["components"]["temperature"] == 0 and item["score"] <= 40


@pytest.mark.django_db
def test_partial_temperature_credit():
    item = score_crop(make_crop(), "N", "tropical", 6, {"avg_temp_c": 20, "avg_monthly_rain_mm": 200})
    assert item["components"]["temperature"] == 50  # (20-18)/(22-18)


@pytest.mark.django_db
def test_without_weather_uses_neutral_values():
    item = score_crop(make_crop(), "N", "tropical", 6, None)
    assert item["components"]["temperature"] is None
    assert item["score"] == 75
    assert any("No weather data" in reason for reason in item["reasons"])


@pytest.mark.django_db
def test_crop_without_rule_for_this_climate_is_excluded_and_counted():
    south_only = make_crop("Southern Crop", rules=(("S", "temperate", "Spring", 9, 11),))
    northern = make_crop("Northern Crop")
    ranked, excluded = rank_crops([south_only, northern], "N", "tropical", 6, IDEAL)
    assert [r["name"] for r in ranked] == ["Northern Crop"] and excluded == 1


@pytest.mark.django_db
def test_ranking_is_best_first_then_alphabetical():
    a = make_crop("Aaa")
    b = make_crop("Bbb")
    c = make_crop("Ccc", rules=(("N", "tropical", "Late", 8, 9),))
    ranked, _ = rank_crops([c, b, a], "N", "tropical", 6, IDEAL)
    assert [r["name"] for r in ranked] == ["Aaa", "Bbb", "Ccc"]


# ------------------------------------------------------------------ weather
class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_weather_is_summarised_and_cached(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return FakeResponse({"daily": {
            "temperature_2m_max": [30, 32], "temperature_2m_min": [20, 22], "precipitation_sum": [1.0, 3.0],
        }})

    monkeypatch.setattr(weather.requests, "get", fake_get)
    first = weather.get_weather_summary(12.97, 77.59)
    second = weather.get_weather_summary(12.98, 77.61)  # same 0.1 degree cell, served from cache
    assert first["avg_temp_c"] == 26.0
    assert first["avg_monthly_rain_mm"] == 60.0  # (1+3)/2 days * 30
    assert first == second and len(calls) == 1


def test_weather_failure_returns_none_and_is_cached_briefly(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError("down")

    monkeypatch.setattr(weather.requests, "get", boom)
    assert weather.get_weather_summary(1.0, 1.0) is None
    assert weather.get_weather_summary(1.0, 1.0) is None
    assert len(calls) == 1