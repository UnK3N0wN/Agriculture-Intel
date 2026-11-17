import logging
import random
import time
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.ai_integration.errors import (
    ProviderUnavailable,
    classify_exception,
    log_provider_failure,
)
from apps.ai_integration.providers import get_provider

from .models import AIJob, DiagnosisLog
from .uploads import read_stored_image

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 5
BACKOFF_MAX_SECONDS = 120
LOCK_SECONDS = 150
STALE_AFTER_MINUTES = 10


def backoff_seconds(retries):
    """Exponential backoff with a little jitter: ~5s, ~10s, ~20s, capped at 120s."""
    base = min(BACKOFF_BASE_SECONDS * (2 ** retries), BACKOFF_MAX_SECONDS)
    return base + random.uniform(0, base * 0.2)


def _claim(job_id):
    """Atomically mark the job as processing. Returns None if there is nothing to do."""
    with transaction.atomic():
        try:
            job = AIJob.objects.select_for_update().get(pk=job_id)
        except AIJob.DoesNotExist:
            return None
        if job.status in (AIJob.Status.SUCCEEDED, AIJob.Status.FAILED):
            return None  # idempotency: already finished
        if job.diagnosis_id:
            job.status = AIJob.Status.SUCCEEDED
            job.save(update_fields=["status"])
            return None
        job.status = AIJob.Status.PROCESSING
        job.attempts += 1
        if job.started_at is None:
            job.started_at = timezone.now()
        job.save(update_fields=["status", "attempts", "started_at"])
        return job


def _run_provider(job):
    provider = get_provider(job.provider)
    image_bytes = read_stored_image(job.image_path)
    mime_type = "image/jpeg"  # every stored image was re-encoded as JPEG

    if provider.supports_async:
        handle = provider.submit(image_bytes, mime_type, job.crop_hint)
        deadline = time.monotonic() + settings.AI_REQUEST_TIMEOUT_SECONDS
        while True:
            result = provider.poll(handle)
            if result is not None:
                return result, provider.model_name
            if time.monotonic() > deadline:
                raise ProviderUnavailable("async poll timed out")
            time.sleep(2)

    return provider.analyze(image_bytes, mime_type, job.crop_hint), provider.model_name


def _save_success(job, result, model_name):
    with transaction.atomic():
        diagnosis = DiagnosisLog.objects.create(
            user_id=job.user_id,
            crop_hint=job.crop_hint,
            image_path=job.image_path,
            image_sha256=job.image_sha256,
            provider=job.provider,
            model_name=model_name,
            **result.to_dict(),
        )
        job.diagnosis = diagnosis
        job.status = AIJob.Status.SUCCEEDED
        job.error_code = ""
        job.error_message = ""
        job.finished_at = timezone.now()
        job.save(update_fields=["diagnosis", "status", "error_code", "error_message", "finished_at"])


def _mark_failed(job, err):
    job.status = AIJob.Status.FAILED
    job.error_code = err.code
    job.error_message = err.user_message[:255]  # safe, user-friendly text only
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_code", "error_message", "finished_at"])


@shared_task(bind=True, name="scans.analyze_scan", max_retries=MAX_RETRIES, acks_late=True)
def analyze_scan(self, job_id):
    lock_key = f"scan:lock:{job_id}"
    # Redis lock: if the broker delivers the same task twice, only one copy runs.
    if not cache.add(lock_key, "1", timeout=LOCK_SECONDS):
        return "locked"
    try:
        job = _claim(job_id)
        if job is None:
            return "skipped"

        try:
            result, model_name = _run_provider(job)
        except SoftTimeLimitExceeded:
            err = ProviderUnavailable("soft time limit exceeded")
        except Exception as exc:  # noqa: BLE001 - converted to a safe error below
            err = classify_exception(exc)
            log_provider_failure(logger, job.provider, exc)
        else:
            _save_success(job, result, model_name)
            return "succeeded"

        logger.warning(
            "Scan job %s attempt %s failed: %s (%s)", job.id, job.attempts, err.code, err.log_detail
        )
        if err.retryable and self.request.retries < self.max_retries:
            cache.delete(lock_key)
            raise self.retry(countdown=backoff_seconds(self.request.retries), exc=err)

        _mark_failed(job, err)
        return "failed"
    finally:
        cache.delete(lock_key)


@shared_task(name="scans.fail_stale_jobs")
def fail_stale_jobs():
    """Safety net run by Celery beat: jobs stuck for too long become 'failed'."""
    cutoff = timezone.now() - timedelta(minutes=STALE_AFTER_MINUTES)
    return AIJob.objects.filter(
        status__in=[AIJob.Status.QUEUED, AIJob.Status.PROCESSING], created_at__lt=cutoff
    ).update(
        status=AIJob.Status.FAILED,
        error_code="timed_out",
        error_message="The analysis took too long. Please try again.",
        finished_at=timezone.now(),
    )


def enqueue_job(job):
    """Send a job to the queue. If Redis is down, fail the job cleanly instead of crashing."""
    try:
        analyze_scan.apply_async(args=[str(job.id)], task_id=job.task_id)
    except Exception:  # noqa: BLE001
        logger.exception("Could not queue scan job %s", job.id)
        AIJob.objects.filter(pk=job.pk).update(
            status=AIJob.Status.FAILED,
            error_code="queue_unavailable",
            error_message="Our analysis queue is unavailable right now. Please try again in a few minutes.",
            finished_at=timezone.now(),
        )