import logging
import math

from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

logger = logging.getLogger(__name__)

DEFAULT_CODES = {403: "permission_denied", 404: "not_found"}


def human_wait(seconds):
    """Turn 900 into '15 minutes', 45 into '45 seconds'."""
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = math.ceil(seconds / 60)
    if minutes < 90:
        return f"{minutes} minutes"
    hours = math.ceil(minutes / 60)
    return f"{hours} hour{'s' if hours != 1 else ''}"


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    # Unexpected crash: log it (secrets redacted), tell the user nothing technical.
    if response is None:
        view = context.get("view")
        logger.exception("Unhandled error in %s", view.__class__.__name__ if view else "unknown view")
        set_rollback()
        return Response(
            {"code": "server_error", "detail": "Something went wrong on our side. Please try again."},
            status=500,
        )

    # Rate limited: one consistent body + Retry-After header.
    if isinstance(exc, Throttled):
        wait = max(1, math.ceil(exc.wait)) if exc.wait is not None else 60
        if exc.get_codes() == "daily_cap_reached":
            code = "daily_cap_reached"
            detail = "You've reached today's scan limit. It resets at midnight UTC."
        else:
            code = "rate_limited"
            detail = f"Too many requests. Please try again in {human_wait(wait)}."
        response.data = {"code": code, "detail": detail, "retry_after_seconds": wait}
        response["Retry-After"] = str(wait)
        return response

    # Add a machine-readable "code" to simple {"detail": "..."} errors.
    if isinstance(response.data, dict) and set(response.data) == {"detail"}:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        code = codes if isinstance(codes, str) else DEFAULT_CODES.get(response.status_code)
        if code:
            response.data["code"] = code

    return response