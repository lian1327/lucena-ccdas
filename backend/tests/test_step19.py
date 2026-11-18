"""Step 19: priority rise after routing, duplicates of ongoing work, time to site, practice data."""
import io
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.analytics import kpis
from apps.cases import services as cs
from apps.cases.models import PriorityLevel
from apps.concerns.models import Concern
from apps.notifications.models import StaffAlert

from .base import SITE, CCADSSTestCase, jpeg, near_site


class PriorityRiseTests(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        self.c = self.make_concern(affected_count=200)
        self.route_to_city(self.c)
        self.accept(self.c)
        self.c.refresh_from_db()
        self.start = self.c.case.priority_level

    def report_again(self, n, start=0):
        for i in range(start, start + n):
            self.make_concern(contact=f"0918{i:07d}", reporter_name=f"Reporter {i}")
        self.c.refresh_from_db()

    def test_more_reporters_flag_a_higher_level_and_alert_the_office_once(self):
        self.assertEqual(self.start.code, "P3")
        self.report_again(9)
        case = self.c.case
        case.refresh_from_db()
        self.assertGreaterEqual(float(self.c.priority_score), 50)
        self.assertEqual(case.priority_rise_to.code, "P2")
        self.assertEqual(case.priority_level.code, "P3")  # the office decides; nothing changes on its own
        alerts = StaffAlert.objects.filter(kind="priority_up", concern=self.c)
        self.assertTrue(alerts.filter(user=self.user("ceo.desk")).exists())
        before = alerts.count()
        self.report_again(1, start=50)
        self.assertEqual(StaffAlert.objects.filter(kind="priority_up", concern=self.c).count(), before)

    def test_setting_or_keeping_the_level_clears_the_flag(self):
        self.report_again(9)
        p2 = PriorityLevel.objects.get(code="P2")
        cs.set_priority(self.c, self.user("ceo.head"), priority_level=p2, reason="Maraming nag-report")
        self.c.case.refresh_from_db()
        self.assertIsNone(self.c.case.priority_rise_to)
        self.assertEqual(self.c.case.priority_level.code, "P2")

    def test_keeping_the_current_level_is_a_decision_too(self):
        self.report_again(9)
        cs.set_priority(self.c, self.user("ceo.head"), priority_level=self.start, reason="Isang lubak lang ito")
        self.c.case.refresh_from_db()
        self.assertIsNone(self.c.case.priority_rise_to)
        self.assertEqual(self.c.case.priority_level.code, "P3")

    def test_flag_is_in_the_case_detail(self):
        from rest_framework.test import APIClient

        self.report_again(9)
        a = APIClient()
        a.force_authenticate(self.user("ceo.head"))
        data = a.get(f"/api/v1/staff/concerns/{self.c.id}/").json()
        self.assertEqual(data["case"]["priority_rise_to"]["code"], "P2")


class OngoingDuplicateTests(CCADSSTestCase):
    def age(self, c, days):
        Concern.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=days))

    def test_report_of_work_in_progress_links_even_when_old(self):
        old = self.make_concern()
        self.route_to_city(old)
        self.age(old, 40)
        new = self.make_concern(contact="09181112222")
        self.assertEqual(new.duplicate_of_id, old.id)

    def test_old_report_never_routed_still_does_not_link(self):
        old = self.make_concern()
        self.age(old, 20)
        new = self.make_concern(contact="09181112222")
        self.assertIsNone(new.duplicate_of_id)

    def test_report_after_work_done_warns_the_validator(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.accept(c)
        cs.assign_person(c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        cs.complete_work(c, self.user("ceo.crew"), remarks="Tapos", photos=[jpeg(2)], photo_meta=[near_site()],
                         before_photos=[jpeg(1)], before_meta=[near_site()])
        self.make_concern(contact="09181112222")
        self.assertTrue(StaffAlert.objects.filter(kind="rereport", concern=c, user=self.user("ceo.rdb.chief")).exists())


class TimeToSiteTests(CCADSSTestCase):
    def test_scorecard_reports_median_hours_to_site(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.accept(c)
        cs.assign_person(c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        cs.arrive(c, self.user("ceo.crew"), latitude=float(SITE[0]), longitude=float(SITE[1]))
        start, end = timezone.now() - timedelta(days=1), timezone.now() + timedelta(days=1)
        rows, city = kpis.scorecard(start, end)
        ceo = next(r for r in rows if r["code"] == "CEO")
        self.assertEqual(ceo["site_checkins"], 1)
        self.assertEqual(ceo["site_checkin_rate"], 1.0)
        self.assertIsNotNone(ceo["median_hours_to_site"])
        self.assertLess(ceo["median_hours_to_site"], 1)


class PracticeDataTests(CCADSSTestCase):
    def test_creates_resets_and_deletes_the_practice_set(self):
        call_command("practice_data", stdout=io.StringIO())
        qs = Concern.objects.filter(is_practice=True)
        self.assertEqual(qs.count(), 11)
        self.assertTrue(qs.filter(status="resolved").exists())
        self.assertTrue(any("c_reused" in c.review_flags for c in qs))
        self.assertFalse(any(c.notify_sms for c in qs))
        call_command("practice_data", "--reset", stdout=io.StringIO())
        self.assertEqual(Concern.objects.filter(is_practice=True).count(), 11)
        call_command("practice_data", "--delete", stdout=io.StringIO())
        self.assertEqual(Concern.objects.filter(is_practice=True).count(), 0)

    @override_settings(CCADSS_SITE_MODE="official")
    def test_refuses_on_the_official_site(self):
        with self.assertRaises(CommandError):
            call_command("practice_data", stdout=io.StringIO())
