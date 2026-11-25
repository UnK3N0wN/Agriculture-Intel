from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

MONTH_VALIDATORS = [MinValueValidator(1), MaxValueValidator(12)]

HEMISPHERE_CHOICES = [("N", "Northern"), ("S", "Southern")]
RULE_HEMISPHERE_CHOICES = HEMISPHERE_CHOICES + [("ANY", "Any")]
CLIMATE_ZONE_CHOICES = [
    ("tropical", "Tropical"),
    ("subtropical", "Subtropical"),
    ("arid", "Arid / semi-arid"),
    ("temperate", "Temperate"),
    ("cold", "Cold"),
]
RULE_CLIMATE_ZONE_CHOICES = CLIMATE_ZONE_CHOICES + [("any", "Any")]


class Location(models.Model):
    """A place a user has saved (a farm, a field) with its derived climate info."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )
    label = models.CharField(max_length=120)
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    country_code = models.CharField(max_length=2, blank=True)
    hemisphere = models.CharField(max_length=1, choices=HEMISPHERE_CHOICES)
    climate_zone = models.CharField(max_length=20, choices=CLIMATE_ZONE_CHOICES)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="loc_user_created_idx"),
            models.Index(fields=["latitude", "longitude"], name="loc_latlon_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="one_default_location_per_user",
            )
        ]

    def __str__(self):
        return f"{self.label} ({self.latitude:.3f}, {self.longitude:.3f})"


class Crop(models.Model):
    class Category(models.TextChoices):
        CEREAL = "cereal", "Cereal"
        PULSE = "pulse", "Pulse"
        VEGETABLE = "vegetable", "Vegetable"
        FRUIT = "fruit", "Fruit"
        OILSEED = "oilseed", "Oilseed"
        FIBRE = "fibre", "Fibre"
        SPICE = "spice", "Spice"
        OTHER = "other", "Other"

    class WaterNeed(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    scientific_name = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField(blank=True)
    water_need = models.CharField(max_length=10, choices=WaterNeed.choices, default=WaterNeed.MEDIUM)
    growing_days_min = models.PositiveSmallIntegerField()
    growing_days_max = models.PositiveSmallIntegerField()
    # Mean daily temperature (deg C) while growing: tolerable range and optimal range.
    temp_min_c = models.FloatField()
    temp_opt_min_c = models.FloatField()
    temp_opt_max_c = models.FloatField()
    temp_max_c = models.FloatField()
    # Rainfall per month (mm) while growing.
    rain_min_mm = models.FloatField()
    rain_max_mm = models.FloatField()
    soil_types = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    source = models.CharField(max_length=60, default="demo")
    source_url = models.URLField(blank=True)
    verified = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "is_active"], name="crop_cat_active_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(temp_min_c__lte=F("temp_opt_min_c"))
                    & Q(temp_opt_min_c__lte=F("temp_opt_max_c"))
                    & Q(temp_opt_max_c__lte=F("temp_max_c"))
                ),
                name="crop_temp_order",
            ),
            models.CheckConstraint(
                condition=Q(rain_min_mm__lte=F("rain_max_mm")), name="crop_rain_order"
            ),
            models.CheckConstraint(
                condition=Q(growing_days_min__lte=F("growing_days_max")), name="crop_days_order"
            ),
        ]

    def __str__(self):
        return self.name


class SeasonalRule(models.Model):
    """When (and where) a crop can be sown. A window may wrap the year end (e.g. Nov to Feb)."""

    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="seasonal_rules")
    hemisphere = models.CharField(max_length=3, choices=RULE_HEMISPHERE_CHOICES, default="ANY")
    climate_zone = models.CharField(max_length=20, choices=RULE_CLIMATE_ZONE_CHOICES, default="any")
    season_label = models.CharField(max_length=40)
    sow_start_month = models.PositiveSmallIntegerField(validators=MONTH_VALIDATORS)
    sow_end_month = models.PositiveSmallIntegerField(validators=MONTH_VALIDATORS)
    suitability_modifier = models.FloatField(
        default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    notes = models.TextField(blank=True)

    source = models.CharField(max_length=60, default="demo")
    verified = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["hemisphere", "climate_zone"], name="rule_hemi_zone_idx"),
            models.Index(fields=["crop", "hemisphere", "climate_zone"], name="rule_crop_hemi_zone_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["crop", "hemisphere", "climate_zone", "season_label"],
                name="unique_rule_per_crop_zone_season",
            )
        ]

    def covers_month(self, month: int) -> bool:
        """True if `month` (1-12) falls inside the sowing window."""
        if self.sow_start_month <= self.sow_end_month:
            return self.sow_start_month <= month <= self.sow_end_month
        return month >= self.sow_start_month or month <= self.sow_end_month

    def __str__(self):
        return f"{self.crop_id}:{self.season_label}"


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="bookmarks")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="bookmark_user_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "crop"], name="unique_bookmark_per_user_crop")
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.crop_id}"

class ClimateNormal(models.Model):
    cell_lat = models.FloatField()
    cell_lon = models.FloatField()
    temp_c = models.JSONField()
    rain_mm = models.JSONField()
    years = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=80)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cell_lat", "cell_lon"], name="unique_climate_cell")
        ]

    def __str__(self):
        return f"Climate {self.cell_lat}, {self.cell_lon}"