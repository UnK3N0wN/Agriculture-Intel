W_SEASON, W_TEMP, W_RAIN = 0.50, 0.35, 0.15
SEASON_CAP = 0.35       # out of season: never better than "poor"
TEMP_CAP = 0.40         # temperature outside the tolerable range
MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_distance(rule, month):
    """Months from `month` to the nearest month of the sowing window (0 = inside)."""
    if rule.covers_month(month):
        return 0
    for step in range(1, 7):
        before = (month - 1 - step) % 12 + 1
        after = (month - 1 + step) % 12 + 1
        if rule.covers_month(before) or rule.covers_month(after):
            return step
    return 6


def _season_component(rules, hemisphere, climate_zone, month):
    applicable = [
        r for r in rules
        if r.hemisphere in (hemisphere, "ANY") and r.climate_zone in (climate_zone, "any")
    ]
    if not applicable:
        return None
    best = None
    for rule in applicable:
        distance = _month_distance(rule, month)
        value = {0: 1.0, 1: 0.5, 2: 0.25}.get(distance, 0.0) * rule.suitability_modifier
        if best is None or value > best[0]:
            best = (value, rule, distance)
    return best


def _temp_component(crop, temp):
    if crop.temp_opt_min_c <= temp <= crop.temp_opt_max_c:
        return 1.0
    if crop.temp_min_c < temp < crop.temp_opt_min_c:
        return (temp - crop.temp_min_c) / (crop.temp_opt_min_c - crop.temp_min_c)
    if crop.temp_opt_max_c < temp < crop.temp_max_c:
        return (crop.temp_max_c - temp) / (crop.temp_max_c - crop.temp_opt_max_c)
    return 0.0


def _rain_component(crop, rain_mm):
    if crop.rain_min_mm <= rain_mm <= crop.rain_max_mm:
        return 1.0
    if rain_mm < crop.rain_min_mm:
        return max(0.0, 1 - (crop.rain_min_mm - rain_mm) / (crop.rain_min_mm * 0.5))
    return max(0.0, 1 - (rain_mm - crop.rain_max_mm) / crop.rain_max_mm)


def _label(score):
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "fair"
    return "poor"


def score_crop(crop, hemisphere, climate_zone, month, weather):
    """Returns a result dict, or None if the crop has no sowing rule for this climate."""
    season = _season_component(list(crop.seasonal_rules.all()), hemisphere, climate_zone, month)
    if season is None:
        return None
    season_value, rule, distance = season

    reasons = []
    window = f"{MONTH_ABBR[rule.sow_start_month]} to {MONTH_ABBR[rule.sow_end_month]}"
    if distance == 0:
        reasons.append(f"This is within the {rule.season_label} sowing window ({window}).")
    elif distance <= 2:
        reasons.append(f"Sowing window ({window}) is {distance} month(s) away.")
    else:
        reasons.append(f"Out of season: the usual sowing window is {window}.")

    if weather:
        temp_value = _temp_component(crop, weather["avg_temp_c"])
        rain_value = _rain_component(crop, weather["avg_monthly_rain_mm"])
        temp_text = f"Average temperature of {weather['avg_temp_c']} C"
        if temp_value >= 1.0:
            reasons.append(f"{temp_text} is ideal for this crop.")
        elif temp_value > 0:
            reasons.append(f"{temp_text} is tolerable but not ideal.")
        else:
            reasons.append(f"{temp_text} is outside what this crop tolerates.")
        rain_text = f"About {int(weather['avg_monthly_rain_mm'])} mm of rain a month"
        if rain_value >= 1.0:
            reasons.append(f"{rain_text} suits this crop.")
        else:
            reasons.append(f"{rain_text} is outside its preferred range; plan irrigation or drainage.")
    else:
        temp_value = rain_value = None  # unknown, so neutral in the total
        reasons.append("No weather data used; the score is based on season and climate zone only.")

    total = (
        W_SEASON * season_value
        + W_TEMP * (0.5 if temp_value is None else temp_value)
        + W_RAIN * (0.5 if rain_value is None else rain_value)
    )
    if season_value == 0:
        total = min(total, SEASON_CAP)
    if temp_value is not None and temp_value == 0:
        total = min(total, TEMP_CAP)
    score = round(total * 100)

    def pct(value):
        return None if value is None else round(value * 100)

    return {
        "crop_id": crop.id,
        "slug": crop.slug,
        "name": crop.name,
        "category": crop.category,
        "water_need": crop.water_need,
        "growing_days": [crop.growing_days_min, crop.growing_days_max],
        "score": score,
        "label": _label(score),
        "season_label": rule.season_label,
        "sow_window": window,
        "components": {
            "season": pct(season_value),
            "temperature": pct(temp_value),
            "rainfall": pct(rain_value),
        },
        "reasons": reasons,
    }


def rank_crops(crops, hemisphere, climate_zone, month, weather):
    """Returns (ranked results, number of crops not applicable to this climate zone)."""
    results, excluded = [], 0
    for crop in crops:
        item = score_crop(crop, hemisphere, climate_zone, month, weather)
        if item is None:
            excluded += 1
        else:
            results.append(item)
    results.sort(key=lambda r: (-r["score"], r["name"]))
    return results, excluded