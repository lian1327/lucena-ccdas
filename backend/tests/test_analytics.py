"""Modules 6–7: KPI index, forecasting model selection, and cohort ("78 of 100 accomplished") statistics."""
from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from apps.analytics import executive as ex
from apps.analytics import kpis
from apps.concerns.models import Concern

from .base import CCADSSTestCase


def metrics(**kw):
    m = {"resolved": 20, "received": 20, "on_time_rate": 1.0, "response_rate": 1.0, "acceptance_rate": 1.0,
         "backlog": 10, "overdue": 0, "quality_rate": 0.0, "p1_cases": 0, "p1_make_safe_rate": None, "aging_30": 0,
         "reopen_rate": 0.0, "proof_rate": 1.0, "citizen_answered": 0, "not_fixed_rate": None, "citizen_not_fixed": 0,
         "recurrence_rate": 0.0}
    m.update(kw)
    return m


class KpiIndexTests(CCADSSTestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(kpis.WEIGHTS.values()), 1.0)

    def test_perfect_office_scores_100_and_good(self):
        r = kpis._index(metrics())
        self.assertEqual((r["index"], r["grade"]), (100.0, "good"))

    def test_index_matches_hand_calculation(self):
        r = kpis._index(metrics(on_time_rate=0.80, response_rate=0.90, acceptance_rate=0.95, overdue=2, quality_rate=0.10))
        expected = 100 * (.40 * .80 + .20 * .90 + .15 * .95 + .15 * (1 - 2 / 10) + .10 * .90)
        self.assertAlmostEqual(r["index"], round(expected, 1))

    def test_low_on_time_needs_attention(self):
        self.assertEqual(kpis._index(metrics(on_time_rate=0.60))["grade"], "attention")

    def test_tiny_sample_is_not_graded(self):
        self.assertEqual(kpis._index(metrics(resolved=3))["grade"], "insufficient")

    def test_on_time_counts_against_the_case_deadline(self):
        now = timezone.now()
        start, end = now - timedelta(days=30), now + timedelta(days=1)

        def case(validated_days_after, due_days_after):
            routed = now - timedelta(days=20)
            return SimpleNamespace(
                routed_at=routed, validated_at=routed + timedelta(days=validated_days_after),
                due_at=routed + timedelta(days=due_days_after), accepted_at=routed, acceptance_due_at=routed + timedelta(days=1),
                responded_at=routed, response_due_at=routed + timedelta(days=1), priority_level=None,
                concern=SimpleNamespace(status="resolved", citizen_confirmed_at=None, citizen_confirmation=""),
                concern_id=validated_days_after * 100 + due_days_after, extended_at=None, escalation_level=0, return_count=0,
            )

        cases = [case(3, 7), case(5, 7), case(10, 7), case(2, 3)]
        q = {"reopened": set(), "recurred": set(), "proof": set(), "overrides": set()}
        m = kpis.compute(cases, start, end, now, q)
        self.assertEqual((m["resolved"], m["on_time"]), (4, 3))
        self.assertAlmostEqual(m["on_time_rate"], 0.75)


class ForecastTests(CCADSSTestCase):
    def test_naive_and_mean3(self):
        self.assertEqual(ex.naive([3, 5, 9])[1], 9)
        self.assertAlmostEqual(ex.mean3([3, 6, 9, 12])[1], 9)

    def test_holt_follows_a_trend(self):
        _, nxt = ex.holt([10, 12, 14, 16, 18, 20])
        self.assertGreater(nxt, 20)

    def test_backtest_is_mean_absolute_percentage_error(self):
        self.assertEqual(ex.backtest([10, 10, 10, 10, 10, 10, 10], ex.naive), 0)
        self.assertAlmostEqual(ex.backtest([10, 10, 10, 20], ex.naive, k=1), 0.5)

    def test_selects_the_method_with_lowest_error(self):
        trend = [10 + 3 * i for i in range(12)]
        f = ex.forecast(trend)
        self.assertEqual(f["method"], "holt")
        self.assertLessEqual(f["backtest_mape"], f["naive_mape"])
        self.assertLessEqual(f["low"], f["estimate"])
        self.assertLessEqual(f["estimate"], f["high"])

    def test_seasonal_wins_on_a_yearly_pattern(self):
        year = [10, 10, 12, 30, 45, 40, 22, 12, 10, 10, 10, 10]  # rainy-season peak
        f = ex.forecast(year * 2)
        self.assertEqual(f["method"], "seasonal")

    def test_seasonal_needs_enough_history(self):
        self.assertNotEqual(ex.forecast([10, 12, 30, 45, 40, 22, 12, 10, 10, 10, 10, 10])["method"], "seasonal")

    def test_short_series_falls_back_to_naive(self):
        self.assertEqual(ex.forecast([4, 6])["method"], "naive")


class CohortTests(CCADSSTestCase):
    def row(self, now, age_days, resolved_after=None, due_after=7, validated_after=None):
        created = now - timedelta(days=age_days)
        resolved = created + timedelta(days=resolved_after) if resolved_after is not None else None
        return {"id": age_days, "created_at": created, "resolved_at": resolved,
                "status": Concern.Status.RESOLVED if resolved else Concern.Status.IN_PROGRESS,
                "category__code": "road_damage", "case__due_at": created + timedelta(days=due_after),
                "case__validated_at": created + timedelta(days=validated_after if validated_after is not None else resolved_after)
                if resolved else None}

    def test_accomplished_and_fair_30_day_rate(self):
        now = timezone.now()
        rows = [self.row(now, 60, 5), self.row(now, 60, 20), self.row(now, 60, 45), self.row(now, 60)]
        s = ex.cohort_stats(rows, now)
        self.assertEqual((s["received"], s["accomplished"], s["open"]), (4, 3, 1))
        self.assertEqual(s["within_30d"], 2)
        self.assertAlmostEqual(s["within_30d_rate"], 0.5)

    def test_open_case_not_yet_due_is_neither_late_nor_on_time(self):
        now = timezone.now()
        rows = [self.row(now, 40, 3), self.row(now, 2, due_after=7)]  # second is open but not yet due
        s = ex.cohort_stats(rows, now)
        self.assertEqual(s["on_time_rate"], 1.0)

    def test_young_cohort_has_no_30_day_rate_yet(self):
        now = timezone.now()
        s = ex.cohort_stats([self.row(now, 5, 2), self.row(now, 3)], now)
        self.assertIsNone(s["within_30d_rate"])


class AnalyticsApiTests(CCADSSTestCase):
    def test_executive_endpoints_for_executives_only(self):
        from rest_framework.test import APIClient

        self.work_until_resolved(self.make_concern())
        api = APIClient()
        api.force_authenticate(self.user("mayor"))
        self.assertEqual(api.get("/api/v1/staff/analytics/executive/").status_code, 200)
        api.force_authenticate(self.user("ceo.crew"))
        self.assertEqual(api.get("/api/v1/staff/analytics/executive/").status_code, 403)
