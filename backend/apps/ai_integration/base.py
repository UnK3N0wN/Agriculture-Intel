import math
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from .errors import ProviderBadResponse

HEALTH_STATUSES = ("healthy", "unhealthy", "unknown")
PATHOGEN_TYPES = ("fungal", "bacterial", "viral", "pest", "nutrient", "none")

_ALIASES = {
    "pathogen_type": {
        "fungus": "fungal", "fungi": "fungal", "bacteria": "bacterial", "virus": "viral",
        "pests": "pest", "insect": "pest", "deficiency": "nutrient",
        "nutrient deficiency": "nutrient", "nutrient_deficiency": "nutrient",
    },
    "health_status": {"diseased": "unhealthy", "disease": "unhealthy", "sick": "unhealthy"},
}
MAX_LIST_ITEMS = 10
MAX_ITEM_CHARS = 400
MAX_NAME_CHARS = 200


def _enum(data, field_name, allowed):
    raw = data.get(field_name)
    if not isinstance(raw, str):
        raise ProviderBadResponse(f"{field_name} is missing or not text")
    value = raw.strip().lower()
    value = _ALIASES.get(field_name, {}).get(value, value)
    if value not in allowed:
        raise ProviderBadResponse(f"{field_name} has an unexpected value")
    return value


def _confidence(raw):
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ProviderBadResponse("confidence is missing or not a number")
    try:
        value = float(raw)
    except ValueError:
        raise ProviderBadResponse("confidence is not a number") from None
    if math.isnan(value) or math.isinf(value):
        raise ProviderBadResponse("confidence is not a finite number")
    if 1 < value <= 100:  # some models answer 87 instead of 0.87
        value /= 100
    return round(min(max(value, 0.0), 1.0), 3)


def _text(raw, limit):
    if not isinstance(raw, str):
        return ""
    return " ".join(raw.split())[:limit]


def _text_list(raw, field_name):
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ProviderBadResponse(f"{field_name} is not a list")
    items = []
    for item in raw:
        if isinstance(item, (str, int, float)) and not isinstance(item, bool):
            cleaned = _text(str(item), MAX_ITEM_CHARS)
            if cleaned:
                items.append(cleaned)
    return items[:MAX_LIST_ITEMS]


@dataclass(frozen=True)
class DiagnosisResult:
    health_status: str
    confidence: float
    common_name: str
    scientific_name: str
    pathogen_type: str
    symptoms: list
    organic_treatment: list
    chemical_treatment: list
    prevention: list

    @classmethod
    def from_dict(cls, data):
        """Strictly validate untrusted provider output. Raises ProviderBadResponse."""
        if not isinstance(data, dict):
            raise ProviderBadResponse("result is not a JSON object")
        health_status = _enum(data, "health_status", HEALTH_STATUSES)
        pathogen_type = _enum(data, "pathogen_type", PATHOGEN_TYPES)
        if health_status == "healthy":
            pathogen_type = "none"
        return cls(
            health_status=health_status,
            confidence=_confidence(data.get("confidence")),
            common_name=_text(data.get("common_name"), MAX_NAME_CHARS),
            scientific_name=_text(data.get("scientific_name"), MAX_NAME_CHARS),
            pathogen_type=pathogen_type,
            symptoms=_text_list(data.get("symptoms"), "symptoms"),
            organic_treatment=_text_list(data.get("organic_treatment"), "organic_treatment"),
            chemical_treatment=_text_list(data.get("chemical_treatment"), "chemical_treatment"),
            prevention=_text_list(data.get("prevention"), "prevention"),
        )

    def to_dict(self):
        return asdict(self)


class BaseAIProvider(ABC):
    """Every provider implements analyze(). Async-style providers also set
    supports_async = True and implement submit() and poll()."""

    name = "base"
    model_name = ""
    supports_async = False

    @abstractmethod
    def analyze(self, image_bytes, mime_type, crop_hint=""):
        """Return a DiagnosisResult, or raise a ProviderError subclass."""

    def submit(self, image_bytes, mime_type, crop_hint=""):
        """Start an async analysis and return a handle (string)."""
        raise NotImplementedError(f"{self.name} does not support async submit()")

    def poll(self, handle):
        """Return a DiagnosisResult when finished, or None while still working."""
        raise NotImplementedError(f"{self.name} does not support async poll()")