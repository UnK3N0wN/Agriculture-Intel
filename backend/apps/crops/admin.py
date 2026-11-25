from django.contrib import admin
from django.utils import timezone

from .models import Bookmark, Crop, Location, SeasonalRule, ClimateNormal

@admin.action(description="Mark selected crops as verified")
def verify_crops(modeladmin, request, queryset):
    queryset.update(verified=True, reviewed_at=timezone.now())


@admin.action(description="Mark selected rules as verified")
def verify_rules(modeladmin, request, queryset):
    queryset.update(verified=True)


@admin.action(description="Hide selected crops from users")
def deactivate(modeladmin, request, queryset):
    queryset.update(is_active=False)

class SeasonalRuleInline(admin.TabularInline):
    model = SeasonalRule
    extra = 0


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "source", "verified", "is_active")
    list_filter = ("category", "water_need", "source", "verified", "is_active")
    search_fields = ("name", "scientific_name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SeasonalRuleInline]
    actions = [verify_crops, deactivate]


@admin.register(SeasonalRule)
class SeasonalRuleAdmin(admin.ModelAdmin):
    list_display = ("crop", "hemisphere", "climate_zone", "season_label", "sow_start_month", "sow_end_month", "source", "verified")
    list_filter = ("hemisphere", "climate_zone", "source", "verified")
    actions = [verify_rules]

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "hemisphere", "climate_zone", "is_default")
    list_filter = ("hemisphere", "climate_zone")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "crop", "created_at")

@admin.register(ClimateNormal)
class ClimateNormalAdmin(admin.ModelAdmin):
    list_display = ("cell_lat", "cell_lon", "years", "source", "fetched_at")