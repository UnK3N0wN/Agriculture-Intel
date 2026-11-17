from dataclasses import dataclass


@dataclass(frozen=True)
class RegionInfo:
    hemisphere: str      # "N" or "S"
    climate_zone: str    # tropical | subtropical | temperate | cold
    region: str          # human label, e.g. "Northern tropics"


_LABELS = {
    "tropical": "tropics",
    "subtropical": "subtropics",
    "temperate": "temperate belt",
    "cold": "cold belt",
}


def classify_location(latitude, longitude=None):
    """Rough latitude-band classification. It cannot see deserts, altitude or microclimates."""
    hemisphere = "N" if latitude >= 0 else "S"
    distance = abs(latitude)
    if distance < 23.5:
        zone = "tropical"
    elif distance < 35:
        zone = "subtropical"
    elif distance < 55:
        zone = "temperate"
    else:
        zone = "cold"
    side = "Northern" if hemisphere == "N" else "Southern"
    return RegionInfo(hemisphere, zone, f"{side} {_LABELS[zone]}")