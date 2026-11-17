import hashlib
from datetime import timedelta

import uuid

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .models import AIJob, DiagnosisLog
from .serializers import ScanSubmitSerializer, DiagnosisSerializer
from .tasks import enqueue_job
from .throttles import DailyAICapThrottle
from .uploads import delete_stored_image, read_stored_image, sanitize_image, store_image

DEDUPE_MINUTES = 10

class ScanSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    # The daily cap goes first so a capped user's requests don't also use up their hourly allowance.
    throttle_classes = [DailyAICapThrottle, UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "ai_submit"  # 10 per hour per user (THROTTLE_AI_SUBMIT)

    def post(self, request):
        serializer = ScanSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = sanitize_image(serializer.validated_data["image"])
        crop_hint = serializer.validated_data.get("crop_hint", "")

        header_key = request.headers.get("Idempotency-Key", "").strip()[:64]
        idempotency_key = header_key or hashlib.sha256(
            f"{image.sha256}|{crop_hint}".encode("utf-8")
        ).hexdigest()

        window_start = timezone.now() - timedelta(minutes=DEDUPE_MINUTES)
        existing = (
            AIJob.objects.filter(
                user=request.user, idempotency_key=idempotency_key, created_at__gte=window_start
            )
            .exclude(status=AIJob.Status.FAILED)
            .first()
        )
        if existing:
            return Response(
                {"task_id": existing.task_id, "status": existing.status},
                status=status.HTTP_202_ACCEPTED,
            )
        relative_path = store_image(request.user.id, image)
        try:
            job = AIJob.objects.create(
                user=request.user,
                task_id=uuid.uuid4().hex,
                idempotency_key=idempotency_key,
                provider=settings.AI_PROVIDER,
                crop_hint=crop_hint,
                image_path=relative_path,
                image_sha256=image.sha256,
            )
        except Exception:
            delete_stored_image(relative_path)  # don't leave orphan files behind
            raise

        transaction.on_commit(lambda: enqueue_job(job))
        return Response({"task_id": job.task_id, "status": job.status}, status=status.HTTP_202_ACCEPTED)

class ScanStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        # Filtering by user means other people's task ids look like "not found" (no information leak).
        job = (
            AIJob.objects.select_related("diagnosis")
            .filter(user=request.user, task_id=task_id)
            .first()
        )
        if job is None:
            raise NotFound("Scan not found.")

        body = {
            "task_id": job.task_id,
            "status": job.status,
            "attempts": job.attempts,
            "error": None,
            "result": None,
        }
        if job.status == AIJob.Status.FAILED:
            body["error"] = {
                "code": job.error_code or "analysis_failed",
                "message": job.error_message or "We couldn't analyze this image. Please try again.",
            }
        elif job.status == AIJob.Status.SUCCEEDED and job.diagnosis:
            body["result"] = DiagnosisSerializer(job.diagnosis).data

        response = Response(body)
        response["Cache-Control"] = "no-store"
        return response


class ScanHistoryListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DiagnosisSerializer

    def get_queryset(self):
        return DiagnosisLog.objects.filter(user=self.request.user)


class ScanHistoryDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DiagnosisSerializer

    def get_queryset(self):
        return DiagnosisLog.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        path = instance.image_path
        instance.delete()
        delete_stored_image(path)  # deleting a diagnosis also deletes the photo


class ScanImageView(APIView):
    """Streams a private image to its owner only. Nginx never serves the folder directly."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        diagnosis = get_object_or_404(DiagnosisLog, pk=pk, user=request.user)
        try:
            data = read_stored_image(diagnosis.image_path)
        except (OSError, ValueError):
            raise NotFound("Image not found.")
        response = HttpResponse(data, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = 'inline; filename="scan.jpg"'
        return response