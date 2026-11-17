def _effective_month(hemisphere, month):
    """For the southern hemisphere, shift by 6 months so one table covers both."""
    return month if hemisphere == "N" else (month + 5) % 12 + 1


def get_season(hemisphere, climate_zone, month):
    m = _effective_month(hemisphere, month)
    if climate_zone == "tropical":
        if 6 <= m <= 9:
            return {"key": "wet", "name": "Wet season"}
        if m >= 10 or m <= 2:
            return {"key": "cool_dry", "name": "Cool dry season"}
        return {"key": "hot_dry", "name": "Hot dry season"}

    if m in (12, 1, 2):
        return {"key": "winter", "name": "Winter"}
    if 3 <= m <= 5:
        return {"key": "spring", "name": "Spring"}
    if 6 <= m <= 8:
        return {"key": "summer", "name": "Summer"}
    return {"key": "autumn", "name": "Autumn"}