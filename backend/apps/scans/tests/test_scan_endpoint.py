from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.scans.models import AIJob

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="farmer", email="f@example.com", password="Str0ng-Passw0rd!x")


def post_scan(api, data, name="leaf.jpg", content_type="image/jpeg", crop_hint="Tomato"):
    return api.post(
        "/api/scans/",
        {"image": SimpleUploadedFile(name, data, content_type=content_type), "crop_hint": crop_hint},
        format="multipart",
    )


def make_job(user, n):
    return AIJob.objects.create(
        user=user, task_id=f"t{n}", idempotency_key=f"k{n}",
        provider="mock", image_path="x", image_sha256="y" * 64,
    )


def test_requires_login(api, make_image):
    assert post_scan(api, make_image()).status_code == 401


def test_valid_upload_is_accepted_and_stored_privately(api, user, make_image, settings):
    api.force_authenticate(user)
    r = post_scan(api, make_image())

    assert r.status_code == 202
    assert set(r.data) == {"task_id", "status"}
    job = AIJob.objects.get(task_id=r.data["task_id"])
    assert job.user == user
    assert job.status == "queued"
    assert job.crop_hint == "Tomato"
    assert job.image_path.startswith(f"scans/{user.id}/")
    assert "leaf" not in job.image_path  # the client's filename is never used
    assert (Path(settings.PRIVATE_MEDIA_ROOT) / job.image_path).is_file()


def test_fake_image_gets_clear_error_code(api, user):
    api.force_authenticate(user)
    r = post_scan(api, b"not an image at all " * 10)
    assert r.status_code == 400
    assert r.data["code"] == "unsupported_type"
    assert AIJob.objects.count() == 0


def test_bad_crop_hint_is_rejected(api, user, make_image):
    api.force_authenticate(user)
    r = post_scan(api, make_image(), crop_hint="<script>alert(1)</script>")
    assert r.status_code == 400
    assert "crop_hint" in r.data


def test_ai_submit_is_limited_per_user(api, user, make_image, settings):
    settings.AI_DAILY_CAP_PER_USER = 1000  # isolate the hourly limit
    limit = int(ScopedRateThrottle.THROTTLE_RATES["ai_submit"].split("/")[0])
    data = make_image()

    api.force_authenticate(user)
    for _ in range(limit):
        assert post_scan(api, data).status_code == 202

    r = post_scan(api, data)
    assert r.status_code == 429
    assert r.data["code"] == "rate_limited"
    assert r.data["retry_after_seconds"] > 0
    assert r["Retry-After"] == str(r.data["retry_after_seconds"])

    other = User.objects.create_user(username="other", email="o@example.com", password="Str0ng-Passw0rd!x")
    api.force_authenticate(other)
    assert post_scan(api, data).status_code == 202


def test_daily_cap_blocks_new_scans(api, user, make_image, settings):
    settings.AI_DAILY_CAP_PER_USER = 2
    make_job(user, 1)
    make_job(user, 2)

    api.force_authenticate(user)
    r = post_scan(api, make_image())
    assert r.status_code == 429
    assert r.data["code"] == "daily_cap_reached"
    assert r.data["retry_after_seconds"] > 0
    assert r["Retry-After"]


def test_jobs_from_previous_days_do_not_count(api, user, make_image, settings):
    settings.AI_DAILY_CAP_PER_USER = 2
    for n in (1, 2):
        job = make_job(user, n)
        AIJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=1))

    api.force_authenticate(user)
    assert post_scan(api, make_image()).status_code == 202