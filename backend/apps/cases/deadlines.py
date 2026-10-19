"""
ARTA (RA 11032) deadlines in WORKING days: weekends and holidays (cases.Holiday) don't count.
Simple 3 · Complex 7 · Highly technical 20. One extension, no longer than the original period,
filed before the original deadline lapses, and the client must be told.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Holiday

SERVICE_CLASS_DAYS = {"simple": 3, "complex": 7, "highly_technical": 20}
END_OF_DAY = time(17, 0)  # office hours end
HOTLINE_8888_HOURS = 72


def add_working_days(start, days):
    """Deadline = end of office hours on the Nth working day after `start`."""
    local = timezone.localtime(start)
    holidays = set(
        Holiday.objects.filter(date__gte=local.date(), date__lte=local.date() + timedelta(days=days * 3 + 14))
        .values_list("date", flat=True)
    )
    d = local.date()
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            added += 1
    return timezone.make_aware(datetime.combine(d, END_OF_DAY), timezone.get_current_timezone())


def working_days_for(concern):
    cat = concern.category
    if not cat:
        return SERVICE_CLASS_DAYS["complex"]
    return cat.sla_days or SERVICE_CLASS_DAYS.get(cat.service_class, 7)


def initial_due(concern, start=None):
    return add_working_days(start or timezone.now(), working_days_for(concern))


def max_extension_due(case):
    """Extension may not exceed the original period, counted from the original deadline."""
    return add_working_days(case.original_due_at or case.due_at, working_days_for(case.concern))
