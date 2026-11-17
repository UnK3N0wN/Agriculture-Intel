from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .anthropic_provider import AnthropicVisionProvider
from .mock_provider import MockProvider
from .plantid_provider import PlantIdProvider

_PROVIDERS = {
    "mock": MockProvider,
    "anthropic": AnthropicVisionProvider,
    "plantid": PlantIdProvider,
}


def get_provider(name=None):
    """Return a provider instance by name (default: the AI_PROVIDER setting)."""
    key = (name or settings.AI_PROVIDER or "").strip().lower()
    try:
        return _PROVIDERS[key]()
    except KeyError:
        raise ImproperlyConfigured(
            f"Unknown AI_PROVIDER '{key}'. Use one of: {', '.join(sorted(_PROVIDERS))}."
        ) from None