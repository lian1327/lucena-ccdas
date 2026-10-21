from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.concerns.models import StatusHistory

from . import services


@receiver(post_save, sender=StatusHistory, dispatch_uid="ccadss_notify_on_history")
def notify_on_history(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        services.on_history(instance)
