from django.urls import path

from . import views_staff as v

urlpatterns = [
    path("points/", v.MapPointsView.as_view(), name="map-points"),
    path("barangays/", v.BarangayStatsView.as_view(), name="map-barangays"),
    path("hotspots/", v.HotspotsView.as_view(), name="map-hotspots"),
    path("boundaries/", v.BoundariesView.as_view(), name="map-boundaries"),
    path("barangays/<int:pk>/puroks/", v.BarangayPuroksView.as_view(), name="map-barangay-puroks"),
]
