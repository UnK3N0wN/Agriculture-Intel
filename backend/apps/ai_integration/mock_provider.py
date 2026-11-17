import hashlib
import time

from django.conf import settings

from .base import BaseAIProvider, DiagnosisResult
from .errors import ProviderBadResponse, ProviderRejectedImage, ProviderUnavailable

DEMO_RESULTS = [
    {
        "health_status": "unhealthy", "confidence": 0.91,
        "common_name": "Early blight", "scientific_name": "Alternaria solani", "pathogen_type": "fungal",
        "symptoms": ["Dark brown spots with concentric rings on older leaves", "Yellowing around the spots", "Leaves drop early"],
        "organic_treatment": ["Remove and destroy infected leaves", "Spray a copper-based or Bacillus subtilis biofungicide", "Mulch to stop soil splashing onto leaves"],
        "chemical_treatment": ["Protectant fungicide such as chlorothalonil or mancozeb, used exactly as the label directs"],
        "prevention": ["Rotate crops every 2 to 3 years", "Water at the base, not over the leaves", "Space plants for airflow"],
    },
    {
        "health_status": "unhealthy", "confidence": 0.86,
        "common_name": "Powdery mildew", "scientific_name": "Erysiphales", "pathogen_type": "fungal",
        "symptoms": ["White powdery coating on the leaf surface", "Leaves curl and turn yellow"],
        "organic_treatment": ["Spray diluted potassium bicarbonate or neem oil", "Remove badly affected leaves"],
        "chemical_treatment": ["Sulfur-based or systemic fungicide, following the label and local rules"],
        "prevention": ["Choose resistant varieties", "Avoid overcrowding", "Water in the morning"],
    },
    {
        "health_status": "unhealthy", "confidence": 0.78,
        "common_name": "Bacterial leaf spot", "scientific_name": "Xanthomonas spp.", "pathogen_type": "bacterial",
        "symptoms": ["Small water-soaked spots that turn dark with a yellow halo", "Spots may merge and the leaf tears"],
        "organic_treatment": ["Remove infected plant parts", "Apply a copper-based bactericide", "Do not work among wet plants"],
        "chemical_treatment": ["Copper bactericide, following label rates and intervals"],
        "prevention": ["Use disease-free seed", "Disinfect tools", "Avoid overhead irrigation"],
    },
    {
        "health_status": "unhealthy", "confidence": 0.74,
        "common_name": "Aphid infestation", "scientific_name": "Aphidoidea", "pathogen_type": "pest",
        "symptoms": ["Clusters of small insects under leaves", "Sticky honeydew and sooty mould", "Curled, distorted new growth"],
        "organic_treatment": ["Spray with a strong jet of water", "Apply insecticidal soap or neem oil", "Encourage ladybirds and lacewings"],
        "chemical_treatment": ["A registered aphicide used strictly as labelled, avoiding flowering periods to protect bees"],
        "prevention": ["Inspect plants weekly", "Avoid over-fertilizing with nitrogen", "Use reflective mulch"],
    },
    {
        "health_status": "healthy", "confidence": 0.95,
        "common_name": "Healthy leaf", "scientific_name": "", "pathogen_type": "none",
        "symptoms": [],
        "organic_treatment": [],
        "chemical_treatment": [],
        "prevention": ["Keep scouting weekly", "Water at the base of the plant", "Maintain balanced soil nutrition"],
    },
]


class MockProvider(BaseAIProvider):
    name = "mock"
    model_name = "mock-v1"

    def analyze(self, image_bytes, mime_type, crop_hint=""):
        delay = float(getattr(settings, "MOCK_DELAY_SECONDS", 0) or 0)
        if delay > 0:
            time.sleep(delay)

        hint = (crop_hint or "").strip().lower()
        if hint == "mock-fail":
            raise ProviderUnavailable("simulated outage")
        if hint == "mock-bad":
            raise ProviderBadResponse("simulated malformed output")
        if hint == "mock-reject":
            raise ProviderRejectedImage("simulated image rejection")

        index = int(hashlib.sha256(image_bytes).hexdigest(), 16) % len(DEMO_RESULTS)
        return DiagnosisResult.from_dict(DEMO_RESULTS[index])