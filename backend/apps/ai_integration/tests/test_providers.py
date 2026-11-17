import anthropic
import httpx
import pytest
import requests
from django.core.exceptions import ImproperlyConfigured

from apps.ai_integration import anthropic_provider, plantid_provider
from apps.ai_integration.anthropic_provider import AnthropicVisionProvider
from apps.ai_integration.errors import (
    ProviderBadResponse,
    ProviderConfigError,
    ProviderUnavailable,
)
from apps.ai_integration.mock_provider import MockProvider
from apps.ai_integration.plantid_provider import PlantIdProvider
from apps.ai_integration.providers import get_provider

GOOD_JSON = (
    '{"health_status": "unhealthy", "confidence": 0.8, "common_name": "Early blight", '
    '"scientific_name": "Alternaria solani", "pathogen_type": "fungal", "symptoms": ["spots"], '
    '"organic_treatment": ["prune"], "chemical_treatment": ["fungicide per label"], "prevention": ["rotate"]}'
)


# ------------------------------------------------------------------ factory
def test_factory_returns_requested_provider(settings):
    settings.AI_PROVIDER = "mock"
    assert isinstance(get_provider(), MockProvider)
    assert isinstance(get_provider("anthropic"), AnthropicVisionProvider)
    assert isinstance(get_provider("PlantID"), PlantIdProvider)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ImproperlyConfigured):
        get_provider("skynet")


# --------------------------------------------------------------------- mock
def test_mock_is_deterministic_per_image():
    provider = MockProvider()
    a = provider.analyze(b"image-one", "image/jpeg")
    b = provider.analyze(b"image-one", "image/jpeg")
    assert a == b


@pytest.mark.parametrize("hint, error", [("mock-fail", ProviderUnavailable), ("mock-bad", ProviderBadResponse)])
def test_mock_can_simulate_failures(hint, error):
    with pytest.raises(error):
        MockProvider().analyze(b"x", "image/jpeg", hint)


# ---------------------------------------------------------------- anthropic
class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeMessage:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [FakeBlock(text)]
        self.stop_reason = stop_reason


class FakeClient:
    captured = None

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error
        self.messages = self

    def create(self, **kwargs):
        FakeClient.captured = kwargs
        if self.error:
            raise self.error
        return self.reply


def patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_: FakeClient(**kwargs))


def test_anthropic_sends_image_prompt_and_parses_json(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = "test-key-123456"
    settings.AI_MODEL = "test-model"
    patch_client(monkeypatch, reply=FakeMessage(GOOD_JSON))

    result = AnthropicVisionProvider().analyze(b"\xff\xd8fake", "image/jpeg", "Tomato")

    sent = FakeClient.captured
    assert sent["model"] == "test-model"
    assert "JSON" in sent["system"]
    blocks = sent["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["media_type"] == "image/jpeg"
    assert "Tomato" in blocks[1]["text"]
    assert result.common_name == "Early blight" and result.pathogen_type == "fungal"


def test_anthropic_tolerates_code_fences(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = "test-key-123456"
    patch_client(monkeypatch, reply=FakeMessage(f"```json\n{GOOD_JSON}\n```"))
    assert AnthropicVisionProvider().analyze(b"x", "image/jpeg").health_status == "unhealthy"


@pytest.mark.parametrize("reply", [FakeMessage("I cannot help"), FakeMessage(GOOD_JSON, stop_reason="max_tokens")])
def test_anthropic_bad_output_is_a_retryable_error(monkeypatch, settings, reply):
    settings.ANTHROPIC_API_KEY = "test-key-123456"
    patch_client(monkeypatch, reply=reply)
    with pytest.raises(ProviderBadResponse) as exc:
        AnthropicVisionProvider().analyze(b"x", "image/jpeg")
    assert exc.value.retryable


def test_anthropic_missing_key_is_a_config_error_with_a_vague_user_message(settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(ProviderConfigError) as exc:
        AnthropicVisionProvider().analyze(b"x", "image/jpeg")
    assert "key" not in exc.value.user_message.lower()


def test_anthropic_timeout_becomes_unavailable(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = "test-key-123456"
    timeout = anthropic.APITimeoutError(request=httpx.Request("POST", "https://example.com"))
    patch_client(monkeypatch, error=timeout)
    with pytest.raises(ProviderUnavailable):
        AnthropicVisionProvider().analyze(b"x", "image/jpeg")


# ----------------------------------------------------------------- plant.id
class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("bad status", response=self)


def plantid(settings, monkeypatch, response):
    settings.PLANTID_API_KEY = "plantid-test-key-1"
    settings.PLANTID_API_URL = "https://example.test/health"
    monkeypatch.setattr(plantid_provider.requests, "post", lambda *a, **k: response)
    return PlantIdProvider()


UNHEALTHY_PAYLOAD = {"result": {
    "is_plant": {"binary": True, "probability": 0.99},
    "is_healthy": {"binary": False, "probability": 0.02},
    "disease": {"suggestions": [
        {"id": "a", "name": "Alternaria solani", "probability": 0.81, "details": {
            "common_names": ["Early blight"], "cause": "Fungi",
            "description": "Dark concentric spots on older leaves.",
            "treatment": {"chemical": ["Apply a protectant fungicide"],
                          "biological": ["Spray a Bacillus subtilis product"],
                          "prevention": ["Rotate crops"]}}},
        {"id": "b", "name": "Other", "probability": 0.1},
    ]},
}}


def test_plantid_unhealthy_is_normalized(settings, monkeypatch):
    result = plantid(settings, monkeypatch, FakeResponse(UNHEALTHY_PAYLOAD)).analyze(b"x", "image/jpeg")
    assert result.health_status == "unhealthy"
    assert result.common_name == "Early blight"
    assert result.scientific_name == "Alternaria solani"
    assert result.pathogen_type == "fungal"
    assert result.confidence == 0.81
    assert "Bacillus" in result.organic_treatment[0]
    assert result.chemical_treatment == ["Apply a protectant fungicide"]


def test_plantid_healthy_and_not_a_plant(settings, monkeypatch):
    healthy = {"result": {"is_plant": {"binary": True, "probability": 0.98}, "is_healthy": {"binary": True, "probability": 0.93}}}
    result = plantid(settings, monkeypatch, FakeResponse(healthy)).analyze(b"x", "image/jpeg")
    assert result.health_status == "healthy" and result.confidence == 0.93

    not_plant = {"result": {"is_plant": {"binary": False, "probability": 0.1}}}
    result = plantid(settings, monkeypatch, FakeResponse(not_plant)).analyze(b"x", "image/jpeg")
    assert result.health_status == "unknown"


def test_plantid_bad_key_is_a_config_error(settings, monkeypatch):
    with pytest.raises(ProviderConfigError):
        plantid(settings, monkeypatch, FakeResponse({}, status=401)).analyze(b"x", "image/jpeg")


def test_plantid_without_result_is_a_bad_response(settings, monkeypatch):
    with pytest.raises(ProviderBadResponse):
        plantid(settings, monkeypatch, FakeResponse({"oops": True})).analyze(b"x", "image/jpeg")