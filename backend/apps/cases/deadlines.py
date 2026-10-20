"""
Deadlines.

ARTA (RA 11032) sets processing-time MAXIMUMS in WORKING days by complexity:
Simple 3 · Complex 7 · Highly technical 20. One extension, no longer than the original period,
filed before the original deadline lapses, with the client notified.

The LGU's priority levels (cases.PriorityLevel) can only tighten this:
  resolution due = clock start + min(priority cap, ARTA class) working days
  response due   = clock start + response hours (calendar) or response working days
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Holiday

SERVICE_CLASS_DAYS = {"simple": 3, "complex": 7, "highly_technical": 20}
END_OF_DAY = time(17, 0)
HOTLINE_8888_HOURS = 72
ACCEPTANCE_WORKING_DAYS = 1  # office must accept or return within 1 working day


def add_working_days(start, days):
    """End of office hours on the Nth working day after `start` (weekends + Holiday table excluded)."""
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


def arta_days(concern):
    cat = concern.category
    if not cat:
        return SERVICE_CLASS_DAYS["complex"]
    return cat.sla_days or SERVICE_CLASS_DAYS.get(cat.service_class, 7)


def resolution_days(concern, level=None):
    days = arta_days(concern)
    if level and level.resolution_cap_days:
        days = min(days, level.resolution_cap_days)
    return days


def resolution_due(concern, start, level=None):
    return add_working_days(start, resolution_days(concern, level))


def response_due(start, level):
    if not level:
        return None
    if level.response_hours:
        return start + timedelta(hours=level.response_hours)
    if level.response_working_days:
        return add_working_days(start, level.response_working_days)
    return None


def acceptance_due(start):
    return add_working_days(start, ACCEPTANCE_WORKING_DAYS)


# Backwards-compatible names used elsewhere
working_days_for = arta_days


def initial_due(concern, start=None, level=None):
    return resolution_due(concern, start or timezone.now(), level)


def max_extension_due(case):
    """Extension may not exceed the original period, counted from the original deadline."""
    return add_working_days(case.original_due_at or case.due_at, resolution_days(case.concern, case.priority_level))
