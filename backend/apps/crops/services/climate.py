import logging
from collections import defaultdict
from datetime import date, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.crops.models import ClimateNormal

logger = logging.getLogger(__name__)

GRID_STEP = 0.25
STALE_AFTER = timedelta(days=365)
FAILURE_CACHE_SECONDS = 300
SOURCE_LABEL = "Open-Meteo historical weather"


def _cell(value):
    return round(round(value / GRID_STEP) * GRID_STEP, 2)


def _fetch(cell_lat, cell_lon):
    years = settings.CLIMATE_NORMALS_YEARS
    end = date(date.today().year - 1, 12, 31)
    start = date(end.year - years + 1, 1, 1)
    params = {
        "latitude": cell_lat,
        "longitude": cell_lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
    }
    if settings.WEATHER_API_KEY:
        params["apikey"] = settings.WEATHER_API_KEY

    response = requests.get(settings.CLIMATE_API_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    daily = response.json()["daily"]

    temp_sum, temp_n = [0.0] * 12, [0] * 12
    rain_by_year_month = defaultdict(float)
    for day, t_max, t_min, rain in zip(
        daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"], daily["precipitation_sum"]
    ):
        year, month = int(day[0:4]), int(day[5:7])
        if t_max is not None and t_min is not None:
            temp_sum[month - 1] += (t_max + t_min) / 2
            temp_n[month - 1] += 1
        if rain is not None:
            rain_by_year_month[(year, month)] += rain

    if min(temp_n) < 1:
        raise ValueError("not enough temperature data")
    temps = [round(temp_sum[i] / temp_n[i], 1) for i in range(12)]

    rain = []
    for month in range(1, 13):
        totals = [total for (_year, m), total in rain_by_year_month.items() if m == month]
        if not totals:
            raise ValueError("not enough rainfall data")
        rain.append(round(sum(totals) / len(totals), 1))
    years_seen = len({year for (year, _m) in rain_by_year_month})
    return temps, rain, years_seen


def _payload(row):
    return {
        "temp_c": row.temp_c,
        "rain_mm": row.rain_mm,
        "years": row.years,
        "source": row.source,
        "cell": {"lat": row.cell_lat, "lon": row.cell_lon},
    }


def get_climate_normals(latitude, longitude):
    """Monthly climate averages for a location, or None if unavailable."""
    cell_lat, cell_lon = _cell(latitude), _cell(longitude)
    row = ClimateNormal.objects.filter(cell_lat=cell_lat, cell_lon=cell_lon).first()
    if row and timezone.now() - row.fetched_at < STALE_AFTER:
        return _payload(row)

    failure_key = f"climate:fail:{cell_lat}:{cell_lon}"
    if cache.get(failure_key):
        return _payload(row) if row else None

    try:
        temps, rain, years = _fetch(cell_lat, cell_lon)
    except Exception as exc:  # noqa: BLE001
        # Log only the exception type: the request URL can contain an API key.
        logger.warning("Climate normals lookup failed: %s", type(exc).__name__)
        cache.set(failure_key, 1, FAILURE_CACHE_SECONDS)
        return _payload(row) if row else None  # a stale answer beats no answer

    row, _ = ClimateNormal.objects.update_or_create(
        cell_lat=cell_lat,
        cell_lon=cell_lon,
        defaults={"temp_c": temps, "rain_mm": rain, "years": years, "source": SOURCE_LABEL, "fetched_at": timezone.now()},
    )
    return _payload(row)


def climate_payload(normals):
    """Shape sent to the frontend chart."""
    if not normals:
        return None
    return {
        "source": normals["source"],
        "years": normals["years"],
        "monthly": [
            {"month": i + 1, "temp_c": normals["temp_c"][i], "rain_mm": normals["rain_mm"][i]}
            for i in range(12)
        ],
    }