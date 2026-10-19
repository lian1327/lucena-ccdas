"""
python manage.py escalate_overdue

Escalates open cases past their due date by one level (Dept Head → City Admin → Mayor).
Schedule it hourly: Windows Task Scheduler in dev, Celery beat or cron in production.
"""
from django.core.management.base import BaseCommand

from apps.cases.services import escalate_overdue


class Command(BaseCommand):
    help = "Escalate overdue open cases one level."

    def handle(self, *args, **opts):
        n = escalate_overdue()
        self.stdout.write(self.style.SUCCESS(f"Escalated {n} overdue case(s)."))
