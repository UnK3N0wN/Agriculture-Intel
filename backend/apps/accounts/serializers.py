import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Profile

User = get_user_model()
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("location_label", "latitude", "longitude", "country_code")

    def validate_latitude(self, value):
        return None if value is None else round(value, 6)

    def validate_longitude(self, value):
        return None if value is None else round(value, 6)

    def validate_country_code(self, value):
        value = value.strip().upper()
        if value and not (len(value) == 2 and value.isalpha()):
            raise serializers.ValidationError("Use a 2-letter country code, e.g. IN.")
        return value

    def validate(self, attrs):
        has_lat = "latitude" in attrs
        has_lon = "longitude" in attrs
        if has_lat != has_lon:
            raise serializers.ValidationError("latitude and longitude must be sent together.")
        if has_lat and (attrs["latitude"] is None) != (attrs["longitude"] is None):
            raise serializers.ValidationError("latitude and longitude must both be set or both be null.")
        return attrs


class MeSerializer(serializers.ModelSerializer):
    """What the API returns about a user."""

    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "date_joined", "profile")
        read_only_fields = fields

    def get_profile(self, obj):
        profile, _ = Profile.objects.get_or_create(user=obj)
        return ProfileSerializer(profile).data


class MeUpdateSerializer(serializers.Serializer):
    """What a user is allowed to change about themselves."""

    email = serializers.EmailField(required=False)
    profile = ProfileSerializer(required=False)

    def validate_email(self, value):
        value = value.strip().lower()
        clash = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists()
        if clash:
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.get("profile")
        with transaction.atomic():
            if "email" in validated_data:
                instance.email = validated_data["email"]
                instance.save(update_fields=["email"])
            if profile_data is not None:
                profile, _ = Profile.objects.get_or_create(user=instance)
                for field, value in profile_data.items():
                    setattr(profile, field, value)
                profile.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=30)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_username(self, value):
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise serializers.ValidationError("Use only letters, numbers, dot, dash and underscore.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is taken.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=validated_data["username"],
                    email=validated_data["email"],
                    password=validated_data["password"],
                )
                Profile.objects.create(user=user)
        except IntegrityError:
            raise serializers.ValidationError({"username": ["This username is taken."]})
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()