from django.apps import AppConfig


class ClassificationConfig(AppConfig):
    name = 'apps.classification'

class ConcernsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.concerns"   # was "concerns"
