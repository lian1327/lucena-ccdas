"""ARTA (RA 11032) clocks are counted in working days: weekends and holidays are skipped."""
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.cases import deadlines
from apps.cases.models import Holiday

from .base import CCADSSTestCase


def manila(y, m, d, h=10):
    return timezone.make_aware(datetime(y, m, d, h, 0), timezone.get_current_timezone())


class WorkingDayTests(CCADSSTestCase):
    def test_skips_weekend(self):
        friday = manila(2026, 10, 23)  # Friday
        due = timezone.localtime(deadlines.add_working_days(friday, 1))
        self.assertEqual(due.date(), date(2026, 10, 26))  # Monday
        self.assertEqual((due.hour, due.minute), (17, 0))  # end of office hours

    def test_three_working_days_from_monday(self):
        self.assertEqual(timezone.localtime(deadlines.add_working_days(manila(2026, 10, 19), 3)).date(), date(2026, 10, 22))

    def test_skips_holiday(self):
        Holiday.objects.update_or_create(date=date(2026, 10, 20), defaults={"name": "Test holiday"})
        due = timezone.localtime(deadlines.add_working_days(manila(2026, 10, 19), 1))
        self.assertEqual(due.date(), date(2026, 10, 21))

    def test_seven_working_days_spans_a_week_and_more(self):
        start = manila(2026, 10, 19)
        due = timezone.localtime(deadlines.add_working_days(start, 7))
        self.assertGreaterEqual((due - start), timedelta(days=9))

    def test_service_classes_match_arta(self):
        self.assertEqual(deadlines.SERVICE_CLASS_DAYS, {"simple": 3, "complex": 7, "highly_technical": 20})

    def test_routed_case_gets_acceptance_and_resolution_deadlines(self):
        c = self.make_concern()
        case = self.route_to_city(c)
        self.assertIsNotNone(case.acceptance_due_at)
        self.assertIsNotNone(case.due_at)
        self.assertGreater(case.due_at, case.acceptance_due_at)
