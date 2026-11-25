from rest_framework import serializers

from .models import Bookmark, Crop, Location, SeasonalRule
from .services.region import classify_location

MAX_LOCATIONS = 10


class SeasonalRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonalRule
        fields = ("hemisphere", "climate_zone", "season_label", "sow_start_month", "sow_end_month", "notes")


class CropSerializer(serializers.ModelSerializer):
    bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Crop
        fields = (
            "id", "name", "slug", "scientific_name", "category", "description", "water_need", "source", "verified",
            "growing_days_min", "growing_days_max", "temp_min_c", "temp_opt_min_c",
            "temp_opt_max_c", "temp_max_c", "rain_min_mm", "rain_max_mm", "soil_types", "bookmarked",
        )
        read_only_fields = fields

    def get_bookmarked(self, obj):
        return obj.id in self.context.get("bookmarked_ids", set())


class CropDetailSerializer(CropSerializer):
    seasonal_rules = SeasonalRuleSerializer(many=True, read_only=True)

    class Meta(CropSerializer.Meta):
        fields = CropSerializer.Meta.fields + ("seasonal_rules",)
        read_only_fields = fields


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = (
            "id", "label", "latitude", "longitude", "country_code",
            "hemisphere", "climate_zone", "is_default", "created_at",
        )
        read_only_fields = ("id", "hemisphere", "climate_zone", "created_at")

    def validate_country_code(self, value):
        value = value.strip().upper()
        if value and not (len(value) == 2 and value.isalpha()):
            raise serializers.ValidationError("Use a 2-letter country code, e.g. IN.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if Location.objects.filter(user=user).count() >= MAX_LOCATIONS:
            raise serializers.ValidationError(f"You can save up to {MAX_LOCATIONS} locations.")
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        info = classify_location(validated_data["latitude"], validated_data["longitude"])
        is_default = validated_data.pop("is_default", False) or not Location.objects.filter(user=user).exists()
        if is_default:
            Location.objects.filter(user=user, is_default=True).update(is_default=False)
        return Location.objects.create(
            user=user,
            hemisphere=info.hemisphere,
            climate_zone=info.climate_zone,
            is_default=is_default,
            **validated_data,
        )


class BookmarkSerializer(serializers.ModelSerializer):
    crop = CropSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ("id", "crop", "note", "created_at")
        read_only_fields = fields