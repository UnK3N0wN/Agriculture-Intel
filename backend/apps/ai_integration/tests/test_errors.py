import pytest
import requests

from apps.ai_integration.errors import (
    ProviderConfigError,
    ProviderError,
    ProviderRateLimited,
    ProviderRejectedImage,
    ProviderUnavailable,
    classify_exception,
)


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError("boom sk-ant-api03-SECRETSECRET", response=response)


@pytest.mark.parametrize(
    "status, expected, retryable",
    [
        (429, ProviderRateLimited, True),
        (500, ProviderUnavailable, True),
        (503, ProviderUnavailable, True),
        (400, ProviderRejectedImage, False),
        (422, ProviderRejectedImage, False),
        (401, ProviderConfigError, False),
        (403, ProviderConfigError, False),
    ],
)
def test_http_status_mapping(status, expected, retryable):
    err = classify_exception(http_error(status))
    assert isinstance(err, expected)
    assert err.retryable is retryable


def test_auth_problems_never_reveal_the_key_issue():
    err = classify_exception(http_error(401))
    text = err.user_message.lower()
    assert "key" not in text and "401" not in text and "auth" not in text


def test_timeouts_are_retryable():
    err = classify_exception(requests.Timeout("slow"))
    assert isinstance(err, ProviderUnavailable) and err.retryable


def test_unknown_errors_never_leak_their_message():
    err = classify_exception(ValueError("secret sk-ant-api03-LEAKYLEAKY"))
    assert isinstance(err, ProviderError)
    assert "sk-ant" not in err.user_message
    assert "sk-ant" not in err.log_detail
    assert not err.retryable