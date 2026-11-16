from django.contrib import admin

from .models import Bookmark, Crop, Location, SeasonalRule


class SeasonalRuleInline(admin.TabularInline):
    model = SeasonalRule
    extra = 0


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "water_need", "is_active")
    list_filter = ("category", "water_need", "is_active")
    search_fields = ("name", "scientific_name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SeasonalRuleInline]


@admin.register(SeasonalRule)
class SeasonalRuleAdmin(admin.ModelAdmin):
    list_display = ("crop", "hemisphere", "climate_zone", "season_label", "sow_start_month", "sow_end_month")
    list_filter = ("hemisphere", "climate_zone")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "hemisphere", "climate_zone", "is_default")
    list_filter = ("hemisphere", "climate_zone")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "crop", "created_at")