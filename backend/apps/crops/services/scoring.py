import math
from statistics import mean

W_SEASON, W_TEMP, W_RAIN = 0.50, 0.35, 0.15
SEASON_CAP = 0.35       # out of season: never better than "poor"
TEMP_CAP = 0.40         # temperature outside the tolerable range
GOOD_FIT = 0.75
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

def cycle_months(crop):
    return max(1, min(12, math.ceil(crop.growing_days_min / 30)))

def cycle_fit(crop, normals, start_month):
    n = cycle_months(crop)
    idx = [(start_month - 1 + i) % 12 for i in range(n)]
    temps = [normals["temp_c"][i] for i in idx]
    rains = [normals["rain_mm"][i] for i in idx]
    t_vals = [_temp_component(crop, t) for t in temps]
    r_vals = [_rain_component(crop, r) for r in rains]
    # The worst month matters: 70% average, 30% weakest month.
    temp = 0.7 * mean(t_vals) + 0.3 * min(t_vals)
    rain = 0.7 * mean(r_vals) + 0.3 * min(r_vals)
    return {
        "months": n,
        "avg_temp_c": round(mean(temps), 1),
        "avg_rain_mm": round(mean(rains)),
        "temp": temp,
        "rain": rain,
        "fit": 0.6 * temp + 0.4 * rain,
    }

def _month_range_text(months):
    months = set(months)
    if not months:
        return ""
    if len(months) == 12:
        return "year-round"
    runs = []
    for m in sorted(months):
        if ((m - 2) % 12 + 1) in months:
            continue  # not the start of a run
        end = m
        while (end % 12 + 1) in months:
            end = end % 12 + 1
        runs.append((m, end))
    return ", ".join(
        MONTH_ABBR[a] if a == b else f"{MONTH_ABBR[a]} to {MONTH_ABBR[b]}" for a, b in runs
    )

def climate_window(crop, normals):
    good = [m for m in range(1, 13) if cycle_fit(crop, normals, m)["fit"] >= GOOD_FIT]
    return _month_range_text(good)


def _temp_verdict(value):
    if value >= 0.99:
        return "ideal"
    return "tolerable but not ideal" if value > 0 else "outside what this crop tolerates"

def score_crop(crop, hemisphere, climate_zone, month, weather, normals=None):
    """Returns a result dict, or None if the crop has no sowing rule for this climate."""
    season = _season_component(list(crop.seasonal_rules.all()), hemisphere, climate_zone, month)
    cycle = cycle_fit(crop, normals, month) if normals else None

    reasons = []
    if season is not None:
        season_value, rule, distance = season
        window = f"{MONTH_ABBR[rule.sow_start_month]} to {MONTH_ABBR[rule.sow_end_month]}"
        season_label, season_source = rule.season_label, "calendar"
        if distance == 0:
            reasons.append(f"This is within the {rule.season_label} sowing window ({window}).")
        elif distance <= 2:
            reasons.append(f"Sowing window ({window}) is {distance} month(s) away.")
        else:
            reasons.append(f"Out of season: the usual sowing window is {window}.")
    elif cycle is not None:
        season_value = cycle["fit"]
        window = climate_window(crop, normals) or "none strongly suited"
        season_label, season_source = "Climate estimate", "climate"
        reasons.append("No local sowing calendar for this crop yet, so the season is estimated from long-term climate averages.")
        reasons.append(f"Best sowing months by climate: {window}.")
    else:
        return None

    if cycle is not None:
        temp_value, rain_value = cycle["temp"], cycle["rain"]
        reasons.append(
            f"Over its roughly {cycle['months']}-month growing period the average temperature is "
            f"{cycle['avg_temp_c']} C, which is {_temp_verdict(temp_value)}."
        )
        if rain_value >= 0.99:
            reasons.append(f"Expected rain of about {cycle['avg_rain_mm']} mm a month suits this crop.")
        else:
            reasons.append(
                f"Expected rain of about {cycle['avg_rain_mm']} mm a month is outside its preferred range; "
                "plan irrigation or drainage."
            )
    elif weather:
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
    if season_source == "calendar" and season_value == 0:
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
        "season_label": season_label,
        "season_source": season_source,
        "sow_window": window,
        "climate_basis": cycle is not None,
        "data": {"source": getattr(crop, "source", "demo"), "verified": getattr(crop, "verified", False)},
        "components": {
            "season": pct(season_value),
            "temperature": pct(temp_value),
            "rainfall": pct(rain_value),
        },
        "reasons": reasons,
    }


def rank_crops(crops, hemisphere, climate_zone, month, weather, normals=None):
    """Returns (ranked results, number of crops not applicable to this climate zone)."""
    results, excluded = [], 0
    for crop in crops:
        item = score_crop(crop, hemisphere, climate_zone, month, weather, normals)
        if item is None:
            excluded += 1
        else:
            results.append(item)
    results.sort(key=lambda r: (-r["score"], r["name"]))
    return results, excluded