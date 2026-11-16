from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.crops.models import Crop, SeasonalRule

# NOTE: demo values, approximate. Verify against your local agricultural
# university / extension service before giving real farming advice.
# rules = (hemisphere, climate_zone, season_label, sow_start_month, sow_end_month)
CROPS = [
    {
        "name": "Rice", "scientific_name": "Oryza sativa", "category": "cereal", "water_need": "high",
        "growing_days_min": 90, "growing_days_max": 150,
        "temp_min_c": 18, "temp_opt_min_c": 22, "temp_opt_max_c": 32, "temp_max_c": 38,
        "rain_min_mm": 100, "rain_max_mm": 300, "soil_types": ["clay", "loam"],
        "description": "Staple cereal grown in flooded or well-watered fields.",
        "rules": [("N", "tropical", "Kharif", 6, 7), ("N", "subtropical", "Kharif", 6, 7), ("S", "tropical", "Wet season", 11, 12)],
    },
    {
        "name": "Wheat", "scientific_name": "Triticum aestivum", "category": "cereal", "water_need": "medium",
        "growing_days_min": 110, "growing_days_max": 150,
        "temp_min_c": 3, "temp_opt_min_c": 12, "temp_opt_max_c": 25, "temp_max_c": 30,
        "rain_min_mm": 30, "rain_max_mm": 100, "soil_types": ["loam", "clay loam"],
        "description": "Cool-season cereal grown for grain.",
        "rules": [("N", "subtropical", "Rabi", 10, 12), ("N", "temperate", "Winter wheat", 9, 10), ("S", "temperate", "Winter", 5, 7)],
    },
    {
        "name": "Maize", "scientific_name": "Zea mays", "category": "cereal", "water_need": "medium",
        "growing_days_min": 80, "growing_days_max": 140,
        "temp_min_c": 10, "temp_opt_min_c": 18, "temp_opt_max_c": 27, "temp_max_c": 35,
        "rain_min_mm": 50, "rain_max_mm": 150, "soil_types": ["loam", "sandy loam"],
        "description": "Versatile cereal used for food, feed and industry.",
        "rules": [("N", "tropical", "Kharif", 6, 7), ("N", "temperate", "Spring", 4, 5), ("S", "temperate", "Spring", 10, 11)],
    },
    {
        "name": "Tomato", "scientific_name": "Solanum lycopersicum", "category": "vegetable", "water_need": "medium",
        "growing_days_min": 90, "growing_days_max": 150,
        "temp_min_c": 10, "temp_opt_min_c": 18, "temp_opt_max_c": 27, "temp_max_c": 35,
        "rain_min_mm": 40, "rain_max_mm": 120, "soil_types": ["loam", "sandy loam"],
        "description": "Warm-season fruiting vegetable; needs good drainage.",
        "rules": [("N", "tropical", "Year-round", 1, 12), ("N", "temperate", "Spring", 3, 5), ("S", "temperate", "Spring", 9, 11)],
    },
    {
        "name": "Potato", "scientific_name": "Solanum tuberosum", "category": "vegetable", "water_need": "medium",
        "growing_days_min": 75, "growing_days_max": 120,
        "temp_min_c": 7, "temp_opt_min_c": 15, "temp_opt_max_c": 22, "temp_max_c": 28,
        "rain_min_mm": 40, "rain_max_mm": 100, "soil_types": ["sandy loam", "loam"],
        "description": "Cool-season tuber crop.",
        "rules": [("N", "subtropical", "Rabi", 10, 11), ("N", "temperate", "Spring", 3, 4), ("S", "temperate", "Spring", 8, 9)],
    },
    {
        "name": "Chickpea", "scientific_name": "Cicer arietinum", "category": "pulse", "water_need": "low",
        "growing_days_min": 95, "growing_days_max": 130,
        "temp_min_c": 5, "temp_opt_min_c": 15, "temp_opt_max_c": 26, "temp_max_c": 35,
        "rain_min_mm": 15, "rain_max_mm": 60, "soil_types": ["loam", "clay loam"],
        "description": "Drought-tolerant winter pulse.",
        "rules": [("N", "subtropical", "Rabi", 10, 11), ("N", "tropical", "Rabi", 10, 11)],
    },
    {
        "name": "Cotton", "scientific_name": "Gossypium hirsutum", "category": "fibre", "water_need": "medium",
        "growing_days_min": 150, "growing_days_max": 200,
        "temp_min_c": 15, "temp_opt_min_c": 21, "temp_opt_max_c": 32, "temp_max_c": 40,
        "rain_min_mm": 60, "rain_max_mm": 150, "soil_types": ["black cotton soil", "loam"],
        "description": "Long-season fibre crop needing warm weather.",
        "rules": [("N", "tropical", "Kharif", 5, 7), ("N", "subtropical", "Kharif", 4, 6)],
    },
    {
        "name": "Groundnut", "scientific_name": "Arachis hypogaea", "category": "oilseed", "water_need": "medium",
        "growing_days_min": 100, "growing_days_max": 140,
        "temp_min_c": 18, "temp_opt_min_c": 22, "temp_opt_max_c": 30, "temp_max_c": 38,
        "rain_min_mm": 50, "rain_max_mm": 125, "soil_types": ["sandy loam", "red loam"],
        "description": "Legume oilseed that prefers light, well-drained soils.",
        "rules": [("N", "tropical", "Kharif", 6, 7)],
    },
    {
        "name": "Finger Millet", "scientific_name": "Eleusine coracana", "category": "cereal", "water_need": "low",
        "growing_days_min": 90, "growing_days_max": 130,
        "temp_min_c": 15, "temp_opt_min_c": 20, "temp_opt_max_c": 30, "temp_max_c": 35,
        "rain_min_mm": 40, "rain_max_mm": 110, "soil_types": ["red loam", "sandy loam"],
        "description": "Hardy, drought-tolerant millet (ragi).",
        "rules": [("N", "tropical", "Kharif", 6, 8)],
    },
    {
        "name": "Okra", "scientific_name": "Abelmoschus esculentus", "category": "vegetable", "water_need": "medium",
        "growing_days_min": 50, "growing_days_max": 90,
        "temp_min_c": 18, "temp_opt_min_c": 24, "temp_opt_max_c": 34, "temp_max_c": 40,
        "rain_min_mm": 50, "rain_max_mm": 130, "soil_types": ["loam", "sandy loam"],
        "description": "Heat-loving vegetable (lady's finger).",
        "rules": [("N", "tropical", "Summer", 2, 3), ("N", "tropical", "Kharif", 6, 7)],
    },
    {
        "name": "Onion", "scientific_name": "Allium cepa", "category": "vegetable", "water_need": "medium",
        "growing_days_min": 100, "growing_days_max": 150,
        "temp_min_c": 10, "temp_opt_min_c": 13, "temp_opt_max_c": 24, "temp_max_c": 35,
        "rain_min_mm": 20, "rain_max_mm": 80, "soil_types": ["loam", "sandy loam"],
        "description": "Bulb vegetable grown in the cooler season.",
        "rules": [("N", "tropical", "Rabi", 10, 12), ("N", "subtropical", "Rabi", 10, 11)],
    },
    {
        "name": "Soybean", "scientific_name": "Glycine max", "category": "oilseed", "water_need": "medium",
        "growing_days_min": 90, "growing_days_max": 130,
        "temp_min_c": 15, "temp_opt_min_c": 20, "temp_opt_max_c": 30, "temp_max_c": 35,
        "rain_min_mm": 60, "rain_max_mm": 150, "soil_types": ["loam", "clay loam"],
        "description": "Nitrogen-fixing legume grown for oil and protein.",
        "rules": [("N", "tropical", "Kharif", 6, 7), ("N", "temperate", "Spring", 5, 6), ("S", "temperate", "Spring", 10, 11)],
    },
]


class Command(BaseCommand):
    help = "Load (or refresh) demo crops and seasonal rules."

    @transaction.atomic
    def handle(self, *args, **options):
        crops_done = rules_done = 0
        for item in CROPS:
            data = dict(item)
            rules = data.pop("rules")
            crop, _ = Crop.objects.update_or_create(slug=slugify(data["name"]), defaults=data)
            crops_done += 1
            for hemisphere, zone, label, start, end in rules:
                SeasonalRule.objects.update_or_create(
                    crop=crop,
                    hemisphere=hemisphere,
                    climate_zone=zone,
                    season_label=label,
                    defaults={"sow_start_month": start, "sow_end_month": end},
                )
                rules_done += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {crops_done} crops and {rules_done} seasonal rules."))