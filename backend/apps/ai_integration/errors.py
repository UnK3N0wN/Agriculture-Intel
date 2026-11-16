import logging

import anthropic
import requests

GENERIC_MESSAGE = "We couldn't analyze this image right now. Please try again in a few minutes."


class ProviderError(Exception):
    """Base error. `user_message` is safe to show; `log_detail` is for our logs only."""

    code = "provider_error"
    user_message = GENERIC_MESSAGE
    retryable = False

    def __init__(self, log_detail=""):
        super().__init__(log_detail)
        self.log_detail = log_detail


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    user_message = "The analysis service is busy or unreachable. We'll retry automatically."
    retryable = True


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limited"
    user_message = "The analysis service is very busy right now. Please try again shortly."
    retryable = True


class ProviderConfigError(ProviderError):
    """Bad or missing API key / permissions. Users must never learn this."""

    code = "provider_misconfigured"
    user_message = "The analysis service is temporarily unavailable. Please try again later."
    retryable = False


class ProviderBadResponse(ProviderError):
    code = "provider_bad_response"
    user_message = "We couldn't read the analysis result. Please try again or use a clearer photo."
    retryable = True


class ProviderRejectedImage(ProviderError):
    code = "image_rejected"
    user_message = (
        "The analysis service couldn't process this image. "
        "Try a clear, well-lit photo of a single leaf."
    )
    retryable = False


def safe_exc_summary(exc):
    """Exception TYPE plus HTTP status only. Never str(exc), which can contain request details."""
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    name = type(exc).__name__
    return f"{name} (status {status})" if status else name


def _from_status(status, summary):
    if status == 429:
        return ProviderRateLimited(summary)
    if status in (401, 403):
        return ProviderConfigError(summary)
    if status in (400, 413, 415, 422):
        return ProviderRejectedImage(summary)
    if status is not None and status >= 500:
        return ProviderUnavailable(summary)
    return ProviderError(summary)


def classify_exception(exc):
    """Turn ANY exception into a ProviderError with a safe user message."""
    if isinstance(exc, ProviderError):
        return exc

    summary = safe_exc_summary(exc)

    # Anthropic SDK
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return ProviderUnavailable(summary)
    if isinstance(exc, anthropic.APIStatusError):
        return _from_status(exc.status_code, summary)

    # requests (Plant.id, weather)
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return ProviderUnavailable(summary)
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        status = response.status_code if response is not None else None
        return _from_status(status, summary)

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return ProviderUnavailable(summary)

    return ProviderError(summary)


def log_provider_failure(logger, provider, exc):
    logger.warning("AI provider '%s' failed: %s", provider, safe_exc_summary(exc))