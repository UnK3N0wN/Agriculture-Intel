from django.urls import path

from .views import ScanSubmitView

urlpatterns = [
    path("", ScanSubmitView.as_view(), name="scan-submit"),
]