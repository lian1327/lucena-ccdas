from django.urls import path

from . import views as v

urlpatterns = [
    path("alerts/", v.AlertListView.as_view(), name="staff-alerts"),
    path("alerts/<int:pk>/read/", v.AlertReadView.as_view(), name="staff-alert-read"),
    path("alerts/read-all/", v.AlertReadAllView.as_view(), name="staff-alerts-read-all"),
    path("notifications/", v.NotificationLogView.as_view(), name="staff-notifications"),
    path("notifications/stats/", v.NotificationStatsView.as_view(), name="staff-notifications-stats"),
    path("notifications/<int:pk>/retry/", v.NotificationRetryView.as_view(), name="staff-notification-retry"),
]
