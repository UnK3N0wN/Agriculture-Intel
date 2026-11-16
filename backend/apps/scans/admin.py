from django.contrib import admin

from .models import AIJob, DiagnosisLog


@admin.register(DiagnosisLog)
class DiagnosisLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "common_name", "health_status", "pathogen_type", "provider", "created_at")
    list_filter = ("health_status", "pathogen_type", "provider")
    readonly_fields = ("id", "created_at")


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("task_id", "user", "status", "provider", "attempts", "created_at")
    list_filter = ("status", "provider")
    readonly_fields = ("id", "created_at", "started_at", "finished_at")