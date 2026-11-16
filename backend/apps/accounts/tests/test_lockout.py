import time

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
PASSWORD = "Str0ng-Passw0rd!x"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def lockout_settings(settings):
    settings.LOGIN_MAX_ATTEMPTS = 5
    settings.LOGIN_LOCKOUT_SECONDS = 900


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="farmer", email="farmer@example.com", password=PASSWORD)


def login(api, username="farmer", password=PASSWORD, ip="10.0.0.1"):
    return api.post(
        "/api/auth/login/",
        {"username": username, "password": password},
        format="json",
        REMOTE_ADDR=ip,
    )


def test_wrong_attempts_count_down(api, user):
    remaining = []
    for _ in range(4):
        r = login(api, password="wrong")
        assert r.status_code == 401
        assert r.data["code"] == "invalid_credentials"
        remaining.append(r.data["attempts_remaining"])
    assert remaining == [4, 3, 2, 1]


def test_fifth_wrong_attempt_locks_with_429(api, user):
    for _ in range(4):
        login(api, password="wrong")
    r = login(api, password="wrong")
    assert r.status_code == 429
    assert r.data["code"] == "login_locked"
    assert 1 <= r.data["retry_after_seconds"] <= 900
    assert r["Retry-After"] == str(r.data["retry_after_seconds"])


def test_correct_password_is_rejected_while_locked(api, user):
    for _ in range(5):
        login(api, password="wrong")
    r = login(api)  # correct password
    assert r.status_code == 429
    assert r.data["code"] == "login_locked"


def test_lock_expires_after_fifteen_minutes(api, user, monkeypatch):
    for _ in range(5):
        login(api, password="wrong")
    assert login(api).status_code == 429

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 901)
    assert login(api).status_code == 200


def test_success_resets_the_counter(api, user):
    for _ in range(3):
        login(api, password="wrong")
    assert login(api).status_code == 200
    r = login(api, password="wrong")
    assert r.status_code == 401
    assert r.data["attempts_remaining"] == 4


def test_lock_is_per_ip(api, user):
    for _ in range(5):
        login(api, password="wrong", ip="10.0.0.1")
    assert login(api, ip="10.0.0.1").status_code == 429
    assert login(api, ip="10.0.0.2").status_code == 200


def test_lock_is_per_username(api, user):
    User.objects.create_user(username="other", email="other@example.com", password=PASSWORD)
    for _ in range(5):
        login(api, username="farmer", password="wrong")
    assert login(api, username="other").status_code == 200


def test_unknown_username_locks_the_same_way(api):
    for _ in range(4):
        assert login(api, username="ghost", password="x").status_code == 401
    r = login(api, username="ghost", password="x")
    assert r.status_code == 429
    assert r.data["code"] == "login_locked"


def test_username_case_does_not_bypass_the_counter(api, user):
    names = ["farmer", "FARMER", "Farmer", "fArMeR", "farmer"]
    codes = [login(api, username=n, password="wrong").status_code for n in names]
    assert codes == [401, 401, 401, 401, 429]