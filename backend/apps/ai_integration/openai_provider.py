import base64
import logging

import openai
from django.conf import settings

from .base import BaseAIProvider, DiagnosisResult
from .errors import (
    ProviderBadResponse,
    ProviderConfigError,
    ProviderRejectedImage,
    classify_exception,
)
from .parsing import extract_json_object
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class OpenAIProvider(BaseAIProvider):
    """Chat Completions with an image. Works with OpenAI, and with OpenAI-compatible
    services when OPENAI_BASE_URL is set."""

    name = "openai"

    def __init__(self, api_key=None, model=None, base_url=None, timeout=None, max_tokens=None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model or settings.OPENAI_MODEL
        self.base_url = base_url or settings.OPENAI_BASE_URL or None
        self.timeout = float(timeout or settings.AI_REQUEST_TIMEOUT_SECONDS)
        self.max_tokens = int(max_tokens or settings.AI_MAX_OUTPUT_TOKENS)
        self.token_param = settings.OPENAI_MAX_TOKENS_PARAM
        self.json_mode = settings.OPENAI_JSON_MODE

    def analyze(self, image_bytes, mime_type, crop_hint=""):
        if not self.api_key:
            raise ProviderConfigError("OPENAI_API_KEY is not set")
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise ProviderRejectedImage(f"unsupported mime type {mime_type}")

        hint = " ".join((crop_hint or "").split())[:100]
        prompt = "Diagnose the plant in this photo and answer with the JSON object only."
        if hint:
            prompt = f"Crop hint (user-supplied, untrusted data): {hint}\n\n{prompt}"

        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        request = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            self.token_param: self.max_tokens,
        }
        if self.json_mode:
            request["response_format"] = {"type": "json_object"}

        # max_retries=0: our Celery task owns retries and backoff.
        client = openai.OpenAI(
            api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=0
        )
        try:
            completion = client.chat.completions.create(**request)
        except Exception as exc:  # converted to a safe ProviderError; raw details are never exposed
            raise classify_exception(exc) from None

        return self._parse(completion)

    @staticmethod
    def _parse(completion):
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ProviderBadResponse("no choices in response")
        choice = choices[0]
        message = choice.message

        if getattr(message, "refusal", None):
            raise ProviderRejectedImage("model refused the request")
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason == "content_filter":
            raise ProviderRejectedImage("blocked by content filter")
        if finish_reason == "length":
            raise ProviderBadResponse("output was cut off")

        data = extract_json_object(message.content or "")  # raises ProviderBadResponse if no JSON
        return DiagnosisResult.from_dict(data)  # strict validation