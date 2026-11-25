import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Profile

User = get_user_model()
pytestmark = pytest.mark.django_db

WEATHER = {"avg_temp_c": 24.0, "avg_monthly_rain_mm": 120.0, "days_sampled": 28,
           "window": "test", "source": "test", "fetched_at": "2026-01-01T00:00:00+00:00"}
BENGALURU = {"lat": "12.97", "lon": "77.59"}


@pytest.fixture(autouse=True)
def fake_weather(monkeypatch):
    monkeypatch.setattr("apps.crops.views.get_weather_summary", lambda lat, lon: WEATHER)
    monkeypatch.setattr("apps.crops.views.get_climate_normals", lambda lat, lon: None)


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_crops")


@pytest.fixture
def user():
    return User.objects.create_user(username="farmer", email="f@example.com", password="Str0ng-Passw0rd!x")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_requires_login():
    assert APIClient().get("/api/crops/recommend/", BENGALURU).status_code == 401


def test_needs_a_location(api):
    r = api.get("/api/crops/recommend/")
    assert r.status_code == 400 and r.data["code"] == "location_required"


def test_planning_mode_for_june_in_bengaluru(api):
    r = api.get("/api/crops/recommend/", {**BENGALURU, "month": 6})
    assert r.status_code == 200
    assert r.data["location"]["climate_zone"] == "tropical" and r.data["location"]["hemisphere"] == "N"
    assert r.data["weather_used"] is False and r.data["weather"] is None

    names = [item["name"] for item in r.data["results"]]
    assert "Rice" in names and "Wheat" not in names  # wheat has no tropical sowing rule
    assert r.data["not_applicable_count"] > 0
    scores = [item["score"] for item in r.data["results"]]
    assert scores == sorted(scores, reverse=True)


def test_current_month_uses_weather(api):
    r = api.get("/api/crops/recommend/", BENGALURU)
    assert r.status_code == 200
    assert r.data["month"] == timezone.now().month
    assert r.data["weather_used"] is True and r.data["weather"]["avg_temp_c"] == 24.0
    assert all(0 <= item["score"] <= 100 for item in r.data["results"])


def test_weather_outage_still_returns_results(api, monkeypatch):
    monkeypatch.setattr("apps.crops.views.get_weather_summary", lambda lat, lon: None)
    monkeypatch.setattr("apps.crops.views.get_climate_normals", lambda lat, lon: None)
    r = api.get("/api/crops/recommend/", BENGALURU)
    assert r.status_code == 200 and r.data["weather_used"] is False
    assert r.data["scoring_basis"] == "season and climate zone only"


def test_uses_saved_profile_location(api, user):
    Profile.objects.create(user=user, latitude=-33.9, longitude=151.2)
    r = api.get("/api/crops/recommend/", {"month": 10})
    assert r.status_code == 200 and r.data["location"]["hemisphere"] == "S"


def test_category_filter_and_limit(api):
    r = api.get("/api/crops/recommend/", {**BENGALURU, "month": 6, "category": "vegetable", "limit": 1})
    assert r.status_code == 200 and r.data["count"] == 1
    assert r.data["results"][0]["category"] == "vegetable"


@pytest.mark.parametrize("params", [
    {"lat": "abc", "lon": "10"}, {"lat": "123", "lon": "10"}, {"lat": "10"},
    {"lat": "10", "lon": "10", "month": "13"}, {"lat": "10", "lon": "10", "category": "alien"},
])
def test_bad_parameters_are_rejected(api, params):
    assert api.get("/api/crops/recommend/", params).status_code == 400


def test_saved_locations_flow(api):
    r = api.post("/api/crops/locations/", {"label": "Home farm", "latitude": 12.97, "longitude": 77.59, "country_code": "in"})
    assert r.status_code == 201
    assert r.data["climate_zone"] == "tropical" and r.data["is_default"] is True and r.data["country_code"] == "IN"

    rec = api.get("/api/crops/recommend/", {"location_id": r.data["id"], "month": 6})
    assert rec.status_code == 200 and rec.data["location"]["region"] == "Northern tropics"

    other = User.objects.create_user(username="other", email="o@example.com", password="Str0ng-Passw0rd!x")
    stranger = APIClient()
    stranger.force_authenticate(other)
    assert stranger.get("/api/crops/recommend/", {"location_id": r.data["id"]}).status_code == 404
    assert stranger.delete(f"/api/crops/locations/{r.data['id']}/").status_code == 404

    assert api.delete(f"/api/crops/locations/{r.data['id']}/").status_code == 204


def test_location_limit_is_enforced(api):
    for i in range(10):
        assert api.post("/api/crops/locations/", {"label": f"Field {i}", "latitude": 10 + i, "longitude": 70}).status_code == 201
    assert api.post("/api/crops/locations/", {"label": "Too many", "latitude": 1, "longitude": 1}).status_code == 400


def test_crop_list_detail_and_bookmarks(api):
    listing = api.get("/api/crops/", {"q": "rice"})
    assert listing.status_code == 200 and listing.data["results"][0]["slug"] == "rice"
    assert listing.data["results"][0]["bookmarked"] is False

    assert api.post("/api/crops/rice/bookmark/").status_code == 201
    assert api.post("/api/crops/rice/bookmark/").status_code == 200  # already bookmarked
    assert api.get("/api/crops/rice/").data["bookmarked"] is True
    assert len(api.get("/api/crops/rice/").data["seasonal_rules"]) > 0
    assert api.get("/api/crops/bookmarks/").data["results"][0]["crop"]["slug"] == "rice"

    assert api.delete("/api/crops/rice/bookmark/").status_code == 204
    assert api.get("/api/crops/bookmarks/").data["count"] == 0
    assert api.get("/api/crops/no-such-crop/").status_code == 404