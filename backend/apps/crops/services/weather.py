import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

FAILURE_MARKER = "unavailable"
FAILURE_CACHE_SECONDS = 300


def _cache_key(latitude, longitude):
    return f"weather:{round(latitude, 1):.1f}:{round(longitude, 1):.1f}"


def _fetch(latitude, longitude):
    params = {
        "latitude": round(latitude, 2),
        "longitude": round(longitude, 2),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "past_days": 14,
        "forecast_days": 14,
        "timezone": "auto",
    }
    if settings.WEATHER_API_KEY:
        params["apikey"] = settings.WEATHER_API_KEY

    response = requests.get(settings.WEATHER_API_BASE_URL, params=params, timeout=8)
    response.raise_for_status()
    daily = response.json()["daily"]

    temps, rains = [], []
    for t_max, t_min, rain in zip(
        daily["temperature_2m_max"], daily["temperature_2m_min"], daily["precipitation_sum"]
    ):
        if t_max is None or t_min is None:
            continue
        temps.append((t_max + t_min) / 2)
        rains.append(rain or 0.0)
    if not temps:
        raise ValueError("no usable weather days")

    return {
        "avg_temp_c": round(sum(temps) / len(temps), 1),
        "avg_monthly_rain_mm": round(sum(rains) / len(rains) * 30, 0),
        "days_sampled": len(temps),
        "window": "last 14 days and next 14 days",
        "source": "open-meteo",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def get_weather_summary(latitude, longitude):
    """Cached weather summary, or None if the weather service is unavailable."""
    key = _cache_key(latitude, longitude)
    cached = cache.get(key)
    if cached == FAILURE_MARKER:
        return None
    if cached:
        return cached

    try:
        summary = _fetch(latitude, longitude)
    except Exception as exc:  # noqa: BLE001
        # Log only the exception type: the request URL can contain the API key.
        logger.warning("Weather lookup failed: %s", type(exc).__name__)
        cache.set(key, FAILURE_MARKER, FAILURE_CACHE_SECONDS)
        return None

    cache.set(key, summary, settings.WEATHER_CACHE_SECONDS)
    return summary