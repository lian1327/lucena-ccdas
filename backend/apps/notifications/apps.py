from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications (SMS, email, staff alerts)"

    def ready(self):
        from . import signals  # noqa: F401
