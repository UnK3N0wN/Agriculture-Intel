from django.urls import path

from .views import (
    BookmarkListView,
    BookmarkToggleView,
    CropDetailView,
    CropListView,
    LocationDeleteView,
    LocationListCreateView,
    RecommendView,
)

urlpatterns = [
    path("", CropListView.as_view(), name="crop-list"),
    path("recommend/", RecommendView.as_view(), name="crop-recommend"),
    path("locations/", LocationListCreateView.as_view(), name="location-list"),
    path("locations/<int:pk>/", LocationDeleteView.as_view(), name="location-delete"),
    path("bookmarks/", BookmarkListView.as_view(), name="bookmark-list"),
    path("<slug:slug>/", CropDetailView.as_view(), name="crop-detail"),
    path("<slug:slug>/bookmark/", BookmarkToggleView.as_view(), name="crop-bookmark"),
]