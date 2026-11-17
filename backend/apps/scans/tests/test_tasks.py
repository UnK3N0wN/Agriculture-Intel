from datetime import timedelta

import pytest
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.ai_integration.base import DiagnosisResult
from apps.ai_integration.errors import ProviderRejectedImage, ProviderUnavailable
from apps.scans import tasks
from apps.scans.models import AIJob, DiagnosisLog
from apps.scans.uploads import sanitize_image, store_image

User = get_user_model()
pytestmark = pytest.mark.django_db

GOOD = DiagnosisResult.from_dict({
    "health_status": "unhealthy", "confidence": 0.9, "common_name": "Early blight",
    "scientific_name": "Alternaria solani", "pathogen_type": "fungal",
    "symptoms": ["spots"], "organic_treatment": ["prune"],
    "chemical_treatment": ["fungicide per label"], "prevention": ["rotate"],
})


class FakeProvider:
    supports_async = False
    model_name = "fake-1"

    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0

    def analyze(self, image_bytes, mime_type, crop_hint=""):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def job(make_image):
    user = User.objects.create_user(username="farmer", email="f@example.com", password="Str0ng-Passw0rd!x")
    image = sanitize_image(SimpleUploadedFile("a.jpg", make_image(), content_type="image/jpeg"))
    return AIJob.objects.create(
        user=user, task_id="t" * 32, idempotency_key="k", provider="mock", crop_hint="Tomato",
        image_path=store_image(user.id, image), image_sha256=image.sha256,
    )


def use_provider(monkeypatch, outcome):
    provider = FakeProvider(outcome)
    monkeypatch.setattr(tasks, "get_provider", lambda name=None: provider)
    return provider


def run(job):
    for attempt in range(tasks.analyze_scan.max_retries + 1):
        try:
            tasks.analyze_scan.apply(
                args=[str(job.id)],
                retries=attempt,
                throw=True,
            )
            break
        except Retry:
            continue
        except Exception:
            break
    job.refresh_from_db()


def test_success_saves_diagnosis(job, monkeypatch):
    provider = use_provider(monkeypatch, GOOD)
    run(job)
    assert job.status == "succeeded" and job.attempts == 1
    assert job.diagnosis.common_name == "Early blight"
    assert job.diagnosis.user_id == job.user_id
    assert job.diagnosis.model_name == "fake-1"
    assert provider.calls == 1


def test_running_twice_does_not_duplicate_or_recall_provider(job, monkeypatch):
    provider = use_provider(monkeypatch, GOOD)
    run(job)
    run(job)
    assert provider.calls == 1
    assert DiagnosisLog.objects.count() == 1


def test_non_retryable_failure_fails_immediately(job, monkeypatch):
    provider = use_provider(monkeypatch, ProviderRejectedImage("secret internal detail"))
    run(job)
    assert job.status == "failed" and job.attempts == 1 and provider.calls == 1
    assert job.error_code == "image_rejected"
    assert "secret" not in job.error_message


def test_retryable_failure_retries_then_gives_up(job, monkeypatch):
    provider = use_provider(monkeypatch, ProviderUnavailable("simulated"))
    run(job)
    assert provider.calls == tasks.MAX_RETRIES + 1
    assert job.status == "failed" and job.attempts == tasks.MAX_RETRIES + 1
    assert job.error_code == "provider_unavailable"


def test_unexpected_errors_never_leak_details(job, monkeypatch):
    use_provider(monkeypatch, RuntimeError("boom sk-ant-api03-LEAKYLEAKY"))
    run(job)
    assert job.status == "failed" and job.error_code == "provider_error"
    assert "sk-ant" not in job.error_message and "boom" not in job.error_message


def test_backoff_grows_exponentially_with_jitter():
    for retries, base in [(0, 5), (1, 10), (2, 20)]:
        assert base <= tasks.backoff_seconds(retries) <= base * 1.2
    assert tasks.backoff_seconds(20) <= tasks.BACKOFF_MAX_SECONDS * 1.2


def test_stale_jobs_are_failed(job):
    AIJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(minutes=30))
    assert tasks.fail_stale_jobs() == 1
    job.refresh_from_db()
    assert job.status == "failed" and job.error_code == "timed_out"


def test_enqueue_failure_marks_job_failed(job, monkeypatch):
    class BrokenTask:
        def apply_async(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(tasks, "analyze_scan", BrokenTask())
    tasks.enqueue_job(job)
    job.refresh_from_db()
    assert job.status == "failed" and job.error_code == "queue_unavailable"