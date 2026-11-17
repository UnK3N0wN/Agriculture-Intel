from django.urls import path

from .views import (
    ScanHistoryDetailView,
    ScanHistoryListView,
    ScanImageView,
    ScanStatusView,
    ScanSubmitView,
)

urlpatterns = [
    path("", ScanSubmitView.as_view(), name="scan-submit"),
    path("status/<str:task_id>/", ScanStatusView.as_view(), name="scan-status"),
    path("history/", ScanHistoryListView.as_view(), name="scan-history"),
    path("history/<uuid:pk>/", ScanHistoryDetailView.as_view(), name="scan-history-detail"),
    path("history/<uuid:pk>/image/", ScanImageView.as_view(), name="scan-image"),
]