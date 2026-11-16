import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
PASSWORD = "Str0ng-Passw0rd!x"

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="farmer", email="farmer@example.com", password=PASSWORD)


def do_login(api, username="farmer", password=PASSWORD):
    return api.post("/api/auth/login/", {"username": username, "password": password}, format="json")


def authenticate(api, access):
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


# ---------------------------------------------------------------- register
def test_register_success_returns_user_and_tokens(api):
    r = api.post(
        "/api/auth/register/",
        {"username": "newfarmer", "email": "New@Example.com", "password": PASSWORD},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["user"]["username"] == "newfarmer"
    assert r.data["user"]["email"] == "new@example.com"
    assert "access" in r.data and "refresh" in r.data
    assert User.objects.get(username="newfarmer").profile is not None


def test_register_rejects_duplicate_username_any_case(api, user):
    r = api.post(
        "/api/auth/register/",
        {"username": "FARMER", "email": "other@example.com", "password": PASSWORD},
        format="json",
    )
    assert r.status_code == 400
    assert "username" in r.data


def test_register_rejects_duplicate_email(api, user):
    r = api.post(
        "/api/auth/register/",
        {"username": "another", "email": "FARMER@example.com", "password": PASSWORD},
        format="json",
    )
    assert r.status_code == 400
    assert "email" in r.data


def test_register_rejects_weak_password(api):
    r = api.post(
        "/api/auth/register/",
        {"username": "weakling", "email": "weak@example.com", "password": "12345678"},
        format="json",
    )
    assert r.status_code == 400
    assert "password" in r.data


# ------------------------------------------------------------------- login
def test_login_success(api, user):
    r = do_login(api)
    assert r.status_code == 200
    assert r.data["user"]["username"] == "farmer"
    assert "access" in r.data and "refresh" in r.data


def test_login_username_is_case_insensitive(api, user):
    assert do_login(api, username="FARMER").status_code == 200


def test_login_wrong_password_returns_401_with_code(api, user):
    r = do_login(api, password="wrong-password")
    assert r.status_code == 401
    assert r.data["code"] == "invalid_credentials"


def test_login_unknown_user_returns_same_401(api):
    r = do_login(api, username="ghost")
    assert r.status_code == 401
    assert r.data["code"] == "invalid_credentials"


# ---------------------------------------------------------------------- me
def test_me_requires_authentication(api):
    assert api.get("/api/auth/me/").status_code == 401


def test_me_returns_profile(api, user):
    authenticate(api, do_login(api).data["access"])
    r = api.get("/api/auth/me/")
    assert r.status_code == 200
    assert r.data["username"] == "farmer"
    assert r.data["profile"]["latitude"] is None


def test_me_patch_saves_location_and_email(api, user):
    authenticate(api, do_login(api).data["access"])
    r = api.patch(
        "/api/auth/me/",
        {
            "email": "New.Farmer@Example.com",
            "profile": {
                "location_label": "Bengaluru",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "country_code": "in",
            },
        },
        format="json",
    )
    assert r.status_code == 200
    assert r.data["email"] == "new.farmer@example.com"
    assert r.data["profile"]["country_code"] == "IN"
    assert r.data["profile"]["latitude"] == 12.9716


def test_me_patch_rejects_latitude_without_longitude(api, user):
    authenticate(api, do_login(api).data["access"])
    r = api.patch("/api/auth/me/", {"profile": {"latitude": 12.9}}, format="json")
    assert r.status_code == 400


def test_me_patch_rejects_out_of_range_latitude(api, user):
    authenticate(api, do_login(api).data["access"])
    r = api.patch("/api/auth/me/", {"profile": {"latitude": 123, "longitude": 10}}, format="json")
    assert r.status_code == 400


# ---------------------------------------------------------- refresh / logout
def test_refresh_rotates_and_blacklists_old_token(api, user):
    old_refresh = do_login(api).data["refresh"]

    r = api.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
    assert r.status_code == 200
    assert r.data["refresh"] != old_refresh
    assert "access" in r.data

    reuse = api.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
    assert reuse.status_code == 401


def test_logout_blacklists_refresh_token(api, user):
    refresh = do_login(api).data["refresh"]

    r = api.post("/api/auth/logout/", {"refresh": refresh}, format="json")
    assert r.status_code == 204

    after = api.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
    assert after.status_code == 401


def test_logout_with_garbage_token_returns_400(api):
    r = api.post("/api/auth/logout/", {"refresh": "not-a-token"}, format="json")
    assert r.status_code == 400
    assert r.data["code"] == "invalid_token"