import re

from rest_framework import serializers

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