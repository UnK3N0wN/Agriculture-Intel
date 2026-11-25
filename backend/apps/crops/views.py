import calendar

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.generics import DestroyAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Profile

from .models import Bookmark, Crop, Location
from .serializers import (
    BookmarkSerializer,
    CropDetailSerializer,
    CropSerializer,
    LocationSerializer,
)
from .services.region import classify_location
from .services.scoring import rank_crops
from .services.season import get_season
from .services.weather import get_weather_summary
from .services.climate import climate_payload, get_climate_normals


class LocationRequired(APIException):
    status_code = 400
    default_code = "location_required"
    default_detail = "Share your location or save one in your profile to get recommendations."


def _parse_float(raw, name, low, high):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: ["Must be a number."]})
    if not (low <= value <= high):
        raise ValidationError({name: [f"Must be between {low} and {high}."]})
    return value


def _parse_int(raw, name, low, high, default):
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: ["Must be a whole number."]})
    if not (low <= value <= high):
        raise ValidationError({name: [f"Must be between {low} and {high}."]})
    return value


class CropListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CropSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Crop.objects.filter(is_active=True)
        category = params.get("category", "").strip().lower()
        if category:
            qs = qs.filter(category=category)
        water = params.get("water_need", "").strip().lower()
        if water:
            qs = qs.filter(water_need=water)
        query = params.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(scientific_name__icontains=query))
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["bookmarked_ids"] = set(
            Bookmark.objects.filter(user=self.request.user).values_list("crop_id", flat=True)
        )
        return context


class CropDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CropDetailSerializer
    lookup_field = "slug"
    queryset = Crop.objects.filter(is_active=True).prefetch_related("seasonal_rules")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["bookmarked_ids"] = set(
            Bookmark.objects.filter(user=self.request.user).values_list("crop_id", flat=True)
        )
        return context


class RecommendView(APIView):
    """GET /api/crops/recommend/?lat=..&lon=.. | ?location_id=.. | (saved profile location)
    optional: month=1-12, category=cereal, limit=1-50"""

    permission_classes = [IsAuthenticated]

    def _coordinates(self, request):
        params = request.query_params

        location_id = params.get("location_id")
        if location_id:
            try:
                location = Location.objects.get(pk=int(location_id), user=request.user)
            except (ValueError, Location.DoesNotExist):
                raise NotFound("Saved location not found.")
            return location.latitude, location.longitude

        if "lat" in params or "lon" in params:
            if "lat" not in params or "lon" not in params:
                raise ValidationError({"lon" if "lat" in params else "lat": ["Send both lat and lon."]})
            return (
                _parse_float(params["lat"], "lat", -90, 90),
                _parse_float(params["lon"], "lon", -180, 180),
            )

        profile = Profile.objects.filter(user=request.user).first()
        if profile and profile.latitude is not None and profile.longitude is not None:
            return profile.latitude, profile.longitude
        raise LocationRequired()

    def get(self, request):
        params = request.query_params
        latitude, longitude = self._coordinates(request)

        current_month = timezone.now().month
        month = _parse_int(params.get("month"), "month", 1, 12, current_month)
        limit = _parse_int(params.get("limit"), "limit", 1, 50, 20)
        category = params.get("category", "").strip().lower()
        if category and category not in Crop.Category.values:
            raise ValidationError({"category": [f"Choose one of: {', '.join(Crop.Category.values)}."]})

        info = classify_location(latitude, longitude)
        season = get_season(info.hemisphere, info.climate_zone, month)
        # Short-term weather describes NOW, so it is only fetched for the current month.
        weather = get_weather_summary(latitude, longitude) if month == current_month else None
        # Long-term climate averages work for ANY month.
        normals = get_climate_normals(latitude, longitude)

        crops = Crop.objects.filter(is_active=True).prefetch_related("seasonal_rules")
        if category:
            crops = crops.filter(category=category)
        ranked, excluded = rank_crops(crops, info.hemisphere, info.climate_zone, month, weather, normals)
        results = ranked[:limit]

        if normals:
            basis = f"{normals['years']}-year climate averages"
        elif weather:
            basis = "season, temperature and rainfall"
        else:
            basis = "season and climate zone only"

        return Response({
            "location": {
                "latitude": round(latitude, 3),
                "longitude": round(longitude, 3),
                "hemisphere": info.hemisphere,
                "climate_zone": info.climate_zone,
                "region": info.region,
            },
            "month": month,
            "month_name": calendar.month_name[month],
            "season": season,
            "weather": weather,
            "weather_used": weather is not None,
            "climate": climate_payload(normals),
            "climate_used": normals is not None,
            "scoring_basis": basis,
            "count": len(results),
            "not_applicable_count": excluded,
            "results": results,
        })


class LocationListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LocationSerializer
    pagination_class = None

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user)


class LocationDeleteView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user)


class BookmarkListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookmarkSerializer

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related("crop")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["bookmarked_ids"] = set(
            Bookmark.objects.filter(user=self.request.user).values_list("crop_id", flat=True)
        )
        return context


class BookmarkToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        crop = get_object_or_404(Crop, slug=slug, is_active=True)
        note = str(request.data.get("note", ""))[:255]
        _, created = Bookmark.objects.get_or_create(
            user=request.user, crop=crop, defaults={"note": note}
        )
        return Response(
            {"bookmarked": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, slug):
        crop = get_object_or_404(Crop, slug=slug, is_active=True)
        Bookmark.objects.filter(user=request.user, crop=crop).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)