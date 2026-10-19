from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = 'apps.analytics'

class ConcernsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.concerns"   # was "concerns"
