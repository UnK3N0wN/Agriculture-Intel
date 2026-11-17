import base64
import logging

import requests
from django.conf import settings

from .base import BaseAIProvider, DiagnosisResult
from .errors import ProviderBadResponse, ProviderConfigError, classify_exception

logger = logging.getLogger(__name__)

_CAUSE_KEYWORDS = [
    ("fungal", ("fung", "mildew", "rust", "blight", "mold", "mould", "rot", "leaf spot", "smut")),
    ("bacterial", ("bacter",)),
    ("viral", ("vir", "mosaic")),
    ("pest", ("pest", "insect", "mite", "aphid", "thrip", "larva", "caterpillar", "nematode", "whitefl", "scale", "beetle")),
    ("nutrient", ("deficien", "nutrient", "nitrogen", "potassium", "phosph", "magnesium", "iron", "calcium")),
]


def guess_pathogen_type(name, cause):
    """Map Plant.id's free-text cause/name onto our fixed list. Cause is checked first."""
    for text in (str(cause or "").lower(), str(name or "").lower()):
        if not text:
            continue
        for pathogen, words in _CAUSE_KEYWORDS:
            if any(word in text for word in words):
                return pathogen
    return "none"


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


class PlantIdProvider(BaseAIProvider):
    """Plant.id 'health assessment' API, normalized into our DiagnosisResult.
    Verify the URL, parameters and response fields against their current docs."""

    name = "plantid"
    model_name = "plant.id-health"

    def __init__(self, api_url=None, api_key=None, timeout=None):
        self.api_url = api_url or settings.PLANTID_API_URL
        self.api_key = api_key or settings.PLANTID_API_KEY
        self.timeout = float(timeout or settings.AI_REQUEST_TIMEOUT_SECONDS)

    def analyze(self, image_bytes, mime_type, crop_hint=""):
        if not self.api_key or not self.api_url:
            raise ProviderConfigError("PLANTID_API_URL / PLANTID_API_KEY not set")

        payload = {"images": [f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"]}
        params = {"details": "common_names,description,treatment,cause,classification"}
        headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(
                self.api_url, params=params, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            body = response.json()
        except ValueError:
            raise ProviderBadResponse("response was not JSON") from None
        except Exception as exc:
            raise classify_exception(exc) from None

        return self._normalize(body)

    @staticmethod
    def _normalize(body):
        result = (body or {}).get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            raise ProviderBadResponse("missing result object")

        is_plant = result.get("is_plant") or {}
        if is_plant.get("binary") is False:
            plant_probability = float(is_plant.get("probability") or 0)
            return DiagnosisResult.from_dict({
                "health_status": "unknown",
                "confidence": 1 - plant_probability,
                "common_name": "No plant detected",
                "scientific_name": "",
                "pathogen_type": "none",
                "symptoms": [],
                "organic_treatment": [],
                "chemical_treatment": [],
                "prevention": ["Retake the photo with one leaf filling most of the frame, in good light."],
            })

        health = result.get("is_healthy") or {}
        healthy_probability = float(health.get("probability") or 0)
        if health.get("binary") is True:
            return DiagnosisResult.from_dict({
                "health_status": "healthy",
                "confidence": healthy_probability,
                "common_name": "Healthy leaf",
                "scientific_name": "",
                "pathogen_type": "none",
                "symptoms": [],
                "organic_treatment": [],
                "chemical_treatment": [],
                "prevention": ["Keep scouting weekly.", "Water at the base of the plant."],
            })

        suggestions = ((result.get("disease") or {}).get("suggestions")) or []
        suggestions = [s for s in suggestions if isinstance(s, dict)]
        if not suggestions:
            return DiagnosisResult.from_dict({
                "health_status": "unhealthy",
                "confidence": 1 - healthy_probability,
                "common_name": "Unidentified problem",
                "scientific_name": "",
                "pathogen_type": "none",
                "symptoms": [],
                "organic_treatment": [],
                "chemical_treatment": [],
                "prevention": ["Consult a local agricultural extension officer with this photo."],
            })

        top = max(suggestions, key=lambda s: float(s.get("probability") or 0))
        details = top.get("details") or {}
        treatment = details.get("treatment") or {}
        name = str(top.get("name") or "").strip()
        common_names = _strings(details.get("common_names"))
        common_name = common_names[0] if common_names else name
        description = details.get("description")

        return DiagnosisResult.from_dict({
            "health_status": "unhealthy",
            "confidence": float(top.get("probability") or 0),
            "common_name": common_name or "Unidentified problem",
            "scientific_name": name if name and name != common_name else "",
            "pathogen_type": guess_pathogen_type(name, details.get("cause")),
            "symptoms": [description[:300]] if isinstance(description, str) and description else [],
            "organic_treatment": _strings(treatment.get("biological")),
            "chemical_treatment": _strings(treatment.get("chemical")),
            "prevention": _strings(treatment.get("prevention")),
        })