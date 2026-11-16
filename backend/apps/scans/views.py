
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .models import AIJob
from .serializers import ScanSubmitSerializer
from .throttles import DailyAICapThrottle
from .uploads import delete_stored_image, sanitize_image, store_image


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
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()[:64] or image.sha256
        relative_path = store_image(request.user.id, image)

        try:
            job = AIJob.objects.create(
                user=request.user,
                task_id=uuid.uuid4().hex,
                idempotency_key=idempotency_key,
                provider=settings.AI_PROVIDER,
                crop_hint=serializer.validated_data.get("crop_hint", ""),
                image_path=relative_path,
                image_sha256=image.sha256,
            )
        except Exception:
            delete_stored_image(relative_path)  # don't leave orphan files behind
            raise

        # Part 4 will queue the background task here. Never return the file path.
        return Response({"task_id": job.task_id, "status": job.status}, status=status.HTTP_202_ACCEPTED)