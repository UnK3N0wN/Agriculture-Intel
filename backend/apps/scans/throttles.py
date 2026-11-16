import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import Throttled
from rest_framework.throttling import BaseThrottle

from .models import AIJob


class DailyAICapThrottle(BaseThrottle):
    """Max AI_DAILY_CAP_PER_USER accepted scans per user per UTC day."""

    def allow_request(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return True  # authentication is enforced by permissions

        now = timezone.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        used = AIJob.objects.filter(user=user, created_at__gte=day_start).count()
        if used < settings.AI_DAILY_CAP_PER_USER:
            return True

        wait = math.ceil((day_start + timedelta(days=1) - now).total_seconds())
        raise Throttled(wait=wait, detail="Daily scan limit reached.", code="daily_cap_reached")