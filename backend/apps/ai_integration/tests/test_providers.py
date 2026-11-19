import types

import httpx
import openai
import pytest
import requests
from django.core.exceptions import ImproperlyConfigured

from apps.ai_integration import openai_provider, plantid_provider
from apps.ai_integration.errors import (
    ProviderBadResponse,
    ProviderConfigError,
    ProviderRateLimited,
    ProviderRejectedImage,
    ProviderUnavailable,
)
from apps.ai_integration.mock_provider import MockProvider
from apps.ai_integration.openai_provider import OpenAIProvider
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
    assert isinstance(get_provider("openai"), OpenAIProvider)
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


# ------------------------------------------------------------------- openai
def completion(text, finish_reason="stop", refusal=None):
    message = types.SimpleNamespace(content=text, refusal=refusal)
    choice = types.SimpleNamespace(finish_reason=finish_reason, message=message)
    return types.SimpleNamespace(choices=[choice])


class FakeClient:
    captured = None

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        FakeClient.captured = kwargs
        if self.error:
            raise self.error
        return self.reply


def patch_client(monkeypatch, **kwargs):
    init_args = {}

    def factory(**init):
        init_args.update(init)
        return FakeClient(**kwargs)

    monkeypatch.setattr(openai_provider.openai, "OpenAI", factory)
    return init_args


@pytest.fixture
def openai_settings(settings):
    settings.OPENAI_API_KEY = "test-key-123456"
    settings.OPENAI_MODEL = "test-model"
    settings.OPENAI_BASE_URL = ""
    settings.OPENAI_MAX_TOKENS_PARAM = "max_completion_tokens"
    settings.OPENAI_JSON_MODE = True
    return settings


def status_error(cls, status, body):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.test/v1/chat"))
    return cls("simulated", response=response, body=body)


def test_openai_sends_image_prompt_and_parses_json(monkeypatch, openai_settings):
    init_args = patch_client(monkeypatch, reply=completion(GOOD_JSON))

    result = OpenAIProvider().analyze(b"\xff\xd8fake", "image/jpeg", "Tomato")

    sent = FakeClient.captured
    assert sent["model"] == "test-model"
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["max_completion_tokens"] == openai_settings.AI_MAX_OUTPUT_TOKENS
    assert sent["messages"][0]["role"] == "system" and "JSON" in sent["messages"][0]["content"]
    text_part, image_part = sent["messages"][1]["content"]
    assert "Tomato" in text_part["text"]
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert init_args["max_retries"] == 0 and init_args["base_url"] is None
    assert result.common_name == "Early blight" and result.pathogen_type == "fungal"


def test_openai_tolerates_code_fences(monkeypatch, openai_settings):
    patch_client(monkeypatch, reply=completion(f"```json\n{GOOD_JSON}\n```"))
    assert OpenAIProvider().analyze(b"x", "image/jpeg").health_status == "unhealthy"


def test_openai_compatible_service_settings(monkeypatch, openai_settings):
    openai_settings.OPENAI_BASE_URL = "https://example.test/v1"
    openai_settings.OPENAI_MAX_TOKENS_PARAM = "max_tokens"
    openai_settings.OPENAI_JSON_MODE = False
    init_args = patch_client(monkeypatch, reply=completion(GOOD_JSON))

    OpenAIProvider().analyze(b"x", "image/jpeg")

    sent = FakeClient.captured
    assert init_args["base_url"] == "https://example.test/v1"
    assert "max_tokens" in sent and "max_completion_tokens" not in sent
    assert "response_format" not in sent


@pytest.mark.parametrize(
    "reply",
    [completion("I cannot help"), completion(GOOD_JSON, finish_reason="length"), types.SimpleNamespace(choices=[])],
)
def test_openai_bad_output_is_a_retryable_error(monkeypatch, openai_settings, reply):
    patch_client(monkeypatch, reply=reply)
    with pytest.raises(ProviderBadResponse) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert exc.value.retryable


@pytest.mark.parametrize(
    "reply",
    [completion(None, refusal="I can't help with that"), completion("", finish_reason="content_filter")],
)
def test_openai_refusals_are_not_retried(monkeypatch, openai_settings, reply):
    patch_client(monkeypatch, reply=reply)
    with pytest.raises(ProviderRejectedImage) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert not exc.value.retryable


def test_openai_missing_key_is_a_config_error_with_a_vague_user_message(openai_settings):
    openai_settings.OPENAI_API_KEY = ""
    with pytest.raises(ProviderConfigError) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert "key" not in exc.value.user_message.lower()


def test_openai_timeout_becomes_unavailable(monkeypatch, openai_settings):
    timeout = openai.APITimeoutError(request=httpx.Request("POST", "https://example.test"))
    patch_client(monkeypatch, error=timeout)
    with pytest.raises(ProviderUnavailable) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert exc.value.retryable


def test_openai_out_of_credits_is_not_retried(monkeypatch, openai_settings):
    error = status_error(openai.RateLimitError, 429, {"code": "insufficient_quota", "message": "quota"})
    patch_client(monkeypatch, error=error)
    with pytest.raises(ProviderConfigError) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert not exc.value.retryable
    assert "quota" not in exc.value.user_message.lower()


def test_openai_normal_rate_limit_is_retried(monkeypatch, openai_settings):
    error = status_error(openai.RateLimitError, 429, {"code": "rate_limit_exceeded", "message": "slow down"})
    patch_client(monkeypatch, error=error)
    with pytest.raises(ProviderRateLimited) as exc:
        OpenAIProvider().analyze(b"x", "image/jpeg")
    assert exc.value.retryable


def test_openai_bad_key_is_a_config_error(monkeypatch, openai_settings):
    error = status_error(openai.AuthenticationError, 401, {"code": "invalid_api_key", "message": "bad key"})
    patch_client(monkeypatch, error=error)
    with pytest.raises(ProviderConfigError):
        OpenAIProvider().analyze(b"x", "image/jpeg")


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