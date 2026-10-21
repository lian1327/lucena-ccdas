"""Module 4: P = 100 × (0.35·S + 0.25·A + 0.20·D + 0.20·T), each component capped at 1."""
import math
from datetime import timedelta

from django.utils import timezone

from apps.concerns.models import Concern
from apps.priority.services import compute_priority, distinct_duplicate_reporters

from .base import CCADSSTestCase


class PriorityTests(CCADSSTestCase):
    def test_formula_matches_hand_calculation(self):
        c = self.make_concern(severity=3, affected_count=50)
        Concern.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=2))
        c.refresh_from_db()
        total = compute_priority(c)
        sla = self.road.sla_days
        S = min(3 / 5 * float(self.road.severity_weight), 1)
        A = min(math.log1p(50) / math.log1p(1000), 1)
        T = min(2 / sla, 1)
        expected = 100 * (0.35 * S + 0.25 * A + 0.20 * 0 + 0.20 * T)
        self.assertAlmostEqual(float(total), expected, delta=0.2)

    def test_score_is_bounded(self):
        c = self.make_concern(severity=5, affected_count=10**6)
        Concern.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=400))
        c.refresh_from_db()
        self.assertLessEqual(float(compute_priority(c)), 100)

    def test_more_people_reporting_raises_priority(self):
        master = self.make_concern(contact="09170000001")
        before = float(master.priority_score)
        for i in range(3):
            self.make_concern(contact=f"0917000001{i}")  # same place, same category → linked duplicates
        master.refresh_from_db()
        self.assertEqual(distinct_duplicate_reporters(master), 3)
        self.assertGreater(float(master.priority_score), before)

    def test_same_person_reporting_twice_counts_once(self):
        master = self.make_concern(contact="09170000001")
        self.make_concern(contact="09170000002")
        self.make_concern(contact="09170000002")
        self.make_concern(contact="09170000001")  # the original reporter again
        self.assertEqual(distinct_duplicate_reporters(master), 1)
