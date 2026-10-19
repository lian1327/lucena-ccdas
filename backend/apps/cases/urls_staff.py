from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_staff as v

router = DefaultRouter()
router.register("concerns", v.StaffConcernViewSet, basename="staff-concern")

urlpatterns = [
    path("summary/", v.StaffSummaryView.as_view(), name="staff-summary"),
    path("departments/", v.DepartmentListView.as_view(), name="staff-departments"),
    path("users/", v.StaffUserListView.as_view(), name="staff-users"),
    path("", include(router.urls)),
]
