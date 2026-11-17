import json
import re

from .errors import ProviderBadResponse

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_MAX_SCAN_ATTEMPTS = 20


def extract_json_object(text):
    """Return the first valid JSON object found in `text`, or raise ProviderBadResponse."""
    if not isinstance(text, str) or not text.strip():
        raise ProviderBadResponse("empty response")

    cleaned = _FENCE.sub("", text.strip()).strip()

    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    start = cleaned.find("{")
    attempts = 0
    while start != -1 and attempts < _MAX_SCAN_ATTEMPTS:
        attempts += 1
        try:
            value, _ = decoder.raw_decode(cleaned[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{", start + 1)

    raise ProviderBadResponse("no valid JSON object in response")