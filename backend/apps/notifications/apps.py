from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'apps.notifications'

class ConcernsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.concerns"   # was "concerns"
