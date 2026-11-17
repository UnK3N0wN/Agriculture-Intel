import re

from rest_framework import serializers

from .models import DiagnosisLog

CROP_HINT_RE = re.compile(r"^[\w ,.'()\-]{1,100}$")


class ScanSubmitSerializer(serializers.Serializer):
    image = serializers.FileField(allow_empty_file=False, max_length=255)
    crop_hint = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def validate_crop_hint(self, value):
        value = " ".join(value.split())  # collapse spaces, drop newlines and tabs
        if value and not CROP_HINT_RE.match(value):
            raise serializers.ValidationError(
                "Crop name may only contain letters, numbers and basic punctuation."
            )
        return value

class DiagnosisSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosisLog
        fields = (
            "id", "crop_hint", "health_status", "confidence", "common_name", "scientific_name",
            "pathogen_type", "symptoms", "organic_treatment", "chemical_treatment", "prevention",
            "image_url", "created_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj):
        return f"/api/scans/history/{obj.id}/image/"