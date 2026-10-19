from django.urls import path

from . import views_public as v

app_name = "public"

urlpatterns = [
    path("categories/", v.PublicCategoryListView.as_view(), name="categories"),
    path("barangays/", v.PublicBarangayListView.as_view(), name="barangays"),
    path("concerns/", v.PublicConcernCreateView.as_view(), name="concern-create"),
    path("concerns/track/<str:reference_no>/", v.PublicTrackView.as_view(), name="concern-track"),
    path("stats/", v.PublicStatsView.as_view(), name="stats"),
]
