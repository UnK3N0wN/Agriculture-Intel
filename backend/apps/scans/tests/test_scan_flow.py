from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.ai_integration.errors import ProviderRejectedImage
from apps.scans import tasks
from apps.scans.models import AIJob, DiagnosisLog
from apps.scans.uploads import sanitize_image, store_image

User = get_user_model()
pytestmark = pytest.mark.django_db
PASSWORD = "Str0ng-Passw0rd!x"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="farmer", email="f@example.com", password=PASSWORD)


@pytest.fixture
def other():
    return User.objects.create_user(username="other", email="o@example.com", password=PASSWORD)


def post_scan(api, data, crop_hint="Tomato", **extra):
    return api.post(
        "/api/scans/",
        {"image": SimpleUploadedFile("leaf.jpg", data, content_type="image/jpeg"), "crop_hint": crop_hint},
        format="multipart",
        **extra,
    )


def make_log(owner, image_bytes=None):
    path = "scans/none.jpg"
    if image_bytes:
        path = store_image(owner.id, sanitize_image(SimpleUploadedFile("a.jpg", image_bytes, content_type="image/jpeg")))
    return DiagnosisLog.objects.create(
        user=owner, image_path=path, image_sha256="a" * 64, health_status="healthy",
        confidence=0.9, provider="mock",
    )


def test_full_flow_submit_then_status_returns_result(api, user, make_image, django_capture_on_commit_callbacks):
    api.force_authenticate(user)
    with django_capture_on_commit_callbacks(execute=True):
        r = post_scan(api, make_image())
    assert r.status_code == 202

    s = api.get(f"/api/scans/status/{r.data['task_id']}/")
    assert s.status_code == 200
    assert s.data["status"] == "succeeded"
    assert s.data["error"] is None
    result = s.data["result"]
    assert result["health_status"] in ("healthy", "unhealthy")
    assert result["image_url"] == f"/api/scans/history/{result['id']}/image/"
    assert s["Cache-Control"] == "no-store"


def test_failed_job_shows_friendly_error(api, user, make_image, monkeypatch, django_capture_on_commit_callbacks):
    provider = type("P", (), {
        "supports_async": False, "model_name": "x",
        "analyze": lambda self, *a, **k: (_ for _ in ()).throw(ProviderRejectedImage("internal detail")),
    })()
    monkeypatch.setattr(tasks, "get_provider", lambda name=None: provider)

    api.force_authenticate(user)
    with django_capture_on_commit_callbacks(execute=True):
        r = post_scan(api, make_image())
    s = api.get(f"/api/scans/status/{r.data['task_id']}/")
    assert s.status_code == 200 and s.data["status"] == "failed"
    assert s.data["error"]["code"] == "image_rejected"
    assert "internal detail" not in s.data["error"]["message"]


def test_status_of_someone_elses_task_is_404(api, user, other, make_image):
    api.force_authenticate(user)
    task_id = post_scan(api, make_image()).data["task_id"]

    api.force_authenticate(other)
    assert api.get(f"/api/scans/status/{task_id}/").status_code == 404
    assert api.get("/api/scans/status/doesnotexist/").status_code == 404


def test_status_requires_login(api):
    assert api.get("/api/scans/status/abc/").status_code == 401


def test_same_photo_twice_returns_same_job(api, user, make_image):
    api.force_authenticate(user)
    data = make_image()
    first = post_scan(api, data)
    second = post_scan(api, data)
    assert first.data["task_id"] == second.data["task_id"]
    assert AIJob.objects.count() == 1


def test_idempotency_key_header_is_honoured(api, user, make_image):
    api.force_authenticate(user)
    first = post_scan(api, make_image(size=(300, 200)), HTTP_IDEMPOTENCY_KEY="abc-123")
    second = post_scan(api, make_image(size=(320, 240)), HTTP_IDEMPOTENCY_KEY="abc-123")
    assert first.data["task_id"] == second.data["task_id"]


def test_history_lists_only_my_diagnoses(api, user, other):
    mine, theirs = make_log(user), make_log(other)
    api.force_authenticate(user)
    r = api.get("/api/scans/history/")
    assert r.status_code == 200
    ids = [item["id"] for item in r.data["results"]]
    assert ids == [str(mine.id)] and str(theirs.id) not in ids


def test_history_detail_is_owner_only(api, user, other):
    log = make_log(user)
    api.force_authenticate(user)
    assert api.get(f"/api/scans/history/{log.id}/").status_code == 200
    api.force_authenticate(other)
    assert api.get(f"/api/scans/history/{log.id}/").status_code == 404
    assert api.delete(f"/api/scans/history/{log.id}/").status_code == 404


def test_image_endpoint_serves_owner_only(api, user, other, make_image):
    log = make_log(user, make_image())
    url = f"/api/scans/history/{log.id}/image/"

    assert api.get(url).status_code == 401
    api.force_authenticate(other)
    assert api.get(url).status_code == 404

    api.force_authenticate(user)
    r = api.get(url)
    assert r.status_code == 200
    assert r["Content-Type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")
    assert r["X-Content-Type-Options"] == "nosniff"


def test_deleting_a_diagnosis_deletes_the_photo(api, user, make_image, settings):
    log = make_log(user, make_image())
    file_path = Path(settings.PRIVATE_MEDIA_ROOT) / log.image_path
    assert file_path.exists()

    api.force_authenticate(user)
    assert api.delete(f"/api/scans/history/{log.id}/").status_code == 204
    assert not file_path.exists()
    assert not DiagnosisLog.objects.filter(pk=log.pk).exists()