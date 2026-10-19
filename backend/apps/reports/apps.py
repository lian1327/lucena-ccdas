from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'apps.reports'

class ConcernsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.concerns"   # was "concerns"
