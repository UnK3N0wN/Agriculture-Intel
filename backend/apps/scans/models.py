import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DiagnosisLog(models.Model):
    """One saved diagnosis result. The id is a random UUID so ids can't be guessed."""

    class HealthStatus(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        UNHEALTHY = "unhealthy", "Unhealthy"
        UNKNOWN = "unknown", "Unknown"

    class PathogenType(models.TextChoices):
        FUNGAL = "fungal", "Fungal"
        BACTERIAL = "bacterial", "Bacterial"
        VIRAL = "viral", "Viral"
        PEST = "pest", "Pest"
        NUTRIENT = "nutrient", "Nutrient deficiency"
        NONE = "none", "None"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diagnoses"
    )
    crop_hint = models.CharField(max_length=100, blank=True)
    # Path relative to PRIVATE_MEDIA_ROOT (never a public URL).
    image_path = models.CharField(max_length=255)
    image_sha256 = models.CharField(max_length=64)
    health_status = models.CharField(max_length=10, choices=HealthStatus.choices)
    confidence = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    common_name = models.CharField(max_length=200, blank=True)
    scientific_name = models.CharField(max_length=200, blank=True)
    pathogen_type = models.CharField(
        max_length=10, choices=PathogenType.choices, default=PathogenType.NONE
    )
    symptoms = models.JSONField(default=list, blank=True)
    organic_treatment = models.JSONField(default=list, blank=True)
    chemical_treatment = models.JSONField(default=list, blank=True)
    prevention = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=30)
    model_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="diag_user_created_idx"),
            models.Index(fields=["health_status"], name="diag_health_idx"),
        ]

    def __str__(self):
        return f"{self.common_name or self.health_status} ({self.id})"


class AIJob(models.Model):
    """Tracks one background analysis from upload to result."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_jobs"
    )
    task_id = models.CharField(max_length=64, unique=True)  # Celery task id
    idempotency_key = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=30)
    crop_hint = models.CharField(max_length=100, blank=True)
    image_path = models.CharField(max_length=255)
    image_sha256 = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    diagnosis = models.OneToOneField(
        DiagnosisLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="job"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="job_user_created_idx"),
            models.Index(fields=["status", "created_at"], name="job_status_created_idx"),
            models.Index(fields=["user", "idempotency_key", "-created_at"], name="job_user_idem_idx"),
        ]

    def __str__(self):
        return f"AIJob<{self.task_id}:{self.status}>"