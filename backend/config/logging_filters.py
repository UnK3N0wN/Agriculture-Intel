import logging
import re

from django.conf import settings

REDACTED = "[REDACTED]"

OPENAI_STYLE_KEY = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
GOOGLE_STYLE_KEY = re.compile(r"AIza[A-Za-z0-9_\-]{20,}")
JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]*")
BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=\-]{8,}")
KEY_VALUE = re.compile(
    r"""(?i)((?:x-api-key|api[_-]?key|apikey|secret|password|token|key)["']?\s*[:=]\s*["']?)[^\s"'&,}]+"""
)


def _known_secrets():
    """Exact secret values from settings (looked up fresh each time)."""
    values = [
        getattr(settings, "SECRET_KEY", ""),
        getattr(settings, "OPENAI_API_KEY", ""),
        getattr(settings, "PLANTID_API_KEY", ""),
        getattr(settings, "WEATHER_API_KEY", ""),
    ]
    try:
        values.append(settings.DATABASES["default"].get("PASSWORD", ""))
    except Exception:
        pass
    return [v for v in values if isinstance(v, str) and len(v) >= 6]


def redact(text):
    for secret in _known_secrets():
        text = text.replace(secret, REDACTED)
    text = OPENAI_STYLE_KEY.sub(REDACTED, text)
    text = GOOGLE_STYLE_KEY.sub(REDACTED, text)
    text = JWT.sub(REDACTED, text)
    text = BEARER.sub(r"\1" + REDACTED, text)
    text = KEY_VALUE.sub(r"\1" + REDACTED, text)
    return text


class RedactSecretsFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = redact(message)
        record.args = ()
        if record.exc_info:
            formatted = record.exc_text or logging.Formatter().formatException(record.exc_info)
            record.exc_text = redact(formatted)
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True