import logging
import sys

from config.logging_filters import RedactSecretsFilter, redact


def make_record(message, *args, exc_info=None):
    return logging.LogRecord("test", logging.ERROR, __file__, 1, message, args, exc_info)


def test_redacts_anthropic_style_keys():
    assert "sk-ant" not in redact("call failed with sk-ant-api03-ABCDEFGH12345678")


def test_redacts_configured_secrets(settings):
    settings.ANTHROPIC_API_KEY = "my-very-secret-provider-key"
    assert "my-very-secret-provider-key" not in redact("oops my-very-secret-provider-key leaked")


def test_redacts_bearer_tokens_and_jwts():
    text = redact(
        "Authorization: Bearer abcdef1234567890 and eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123_-"
    )
    assert "abcdef1234567890" not in text
    assert "eyJhbGci" not in text


def test_redacts_key_value_pairs():
    assert "abcd1234" not in redact("params: api_key=abcd1234&page=1")


def test_filter_cleans_arguments_and_tracebacks(settings):
    settings.PLANTID_API_KEY = "plantid-secret-123456"
    try:
        raise RuntimeError("request failed for plantid-secret-123456")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = make_record("Provider error: %s", "plantid-secret-123456", exc_info=exc_info)
    assert RedactSecretsFilter().filter(record) is True
    assert "plantid-secret-123456" not in record.getMessage()
    assert "plantid-secret-123456" not in record.exc_text