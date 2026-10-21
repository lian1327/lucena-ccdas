"""Many people, one problem: duplicates link to one master case; a returning problem is a recurrence."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.cases import services as cs
from apps.concerns.models import Concern
from apps.concerns.services import find_master_duplicate, find_recurrence

from .base import SITE, CCADSSTestCase

S = Concern.Status


class DuplicateTests(CCADSSTestCase):
    def test_same_category_within_100m_links(self):
        a = self.make_concern()
        b = self.make_concern(lat=SITE[0] + Decimal("0.0005"))  # ≈ 55 m north
        self.assertEqual(b.duplicate_of_id, a.pk)

    def test_far_away_does_not_link(self):
        self.make_concern()
        b = self.make_concern(lat=SITE[0] + Decimal("0.0020"))  # ≈ 220 m
        self.assertIsNone(b.duplicate_of_id)

    def test_other_category_does_not_link(self):
        self.make_concern()
        b = self.make_concern(category=self.light)
        self.assertIsNone(b.duplicate_of_id)

    def test_older_than_14_days_does_not_link(self):
        a = self.make_concern()
        Concern.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=15))
        b = self.make_concern()
        self.assertIsNone(b.duplicate_of_id)

    def test_closed_case_is_not_a_master(self):
        a = self.make_concern()
        Concern.objects.filter(pk=a.pk).update(status=S.CLOSED)
        b = self.make_concern(submit=False)
        self.assertIsNone(find_master_duplicate(b))

    def test_duplicates_follow_the_master_status(self):
        a = self.make_concern()
        b = self.make_concern(contact="09179999999")
        self.route_to_city(a)
        b.refresh_from_db()
        self.assertEqual(b.status, S.ASSIGNED)
        self.assertTrue(b.history.filter(to_status=S.ASSIGNED, remarks__contains=a.reference_no).exists())

    def test_link_and_unlink_by_staff(self):
        a = self.make_concern()
        b = self.make_concern(lat=SITE[0] + Decimal("0.01"))
        cs.link_duplicate(b, a, self.user("pacd.desk"))
        b.refresh_from_db()
        self.assertEqual(b.duplicate_of_id, a.pk)
        cs.unlink_duplicate(b, self.user("pacd.desk"))
        b.refresh_from_db()
        self.assertIsNone(b.duplicate_of_id)


class RecurrenceTests(CCADSSTestCase):
    def test_problem_back_after_fix_is_flagged(self):
        fixed = self.make_concern()
        Concern.objects.filter(pk=fixed.pk).update(status=S.RESOLVED, resolved_at=timezone.now() - timedelta(days=10))
        again = self.make_concern()
        self.assertEqual(again.recurrence_of_id, fixed.pk)
        self.assertIsNone(again.duplicate_of_id)

    def test_fix_older_than_30_days_is_not_a_recurrence(self):
        fixed = self.make_concern()
        Concern.objects.filter(pk=fixed.pk).update(status=S.RESOLVED, resolved_at=timezone.now() - timedelta(days=45))
        again = self.make_concern(submit=False)
        self.assertIsNone(find_recurrence(again, now=timezone.now()))
