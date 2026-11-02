"""Field view (Step 18): job list, on-site check-in, "can't finish yet", live-camera photos."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.cases import services as cs
from apps.cases.models import Case, SiteVisit
from apps.notifications.models import StaffAlert

from .base import CCADSSTestCase, jpeg, near_site


class FieldBase(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        self.c = self.make_concern()
        self.route_to_city(self.c)
        self.accept(self.c)
        cs.assign_person(self.c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        self.c.refresh_from_db()

    def api(self, username):
        a = APIClient()
        a.force_authenticate(self.user(username))
        return a


class FieldJobsTests(FieldBase):
    def ids(self, username):
        r = self.api(username).get("/api/v1/staff/field/jobs/")
        self.assertEqual(r.status_code, 200, r.content)
        return [j["id"] for j in r.json()]

    def test_assigned_worker_and_division_mate_see_the_job(self):
        self.assertIn(self.c.id, self.ids("ceo.crew"))
        self.assertIn(self.c.id, self.ids("ceo.staff"))  # same division (CEO-RDB)

    def test_other_office_and_desk_do_not(self):
        self.assertNotIn(self.c.id, self.ids("gso.crew"))
        self.assertNotIn(self.c.id, self.ids("ceo.desk"))

    def test_job_leaves_the_list_once_work_is_reported(self):
        cs.complete_work(self.c, self.user("ceo.crew"), remarks="Tapos", photos=[jpeg(2)], photo_meta=[near_site()],
                         before_photos=[jpeg(1)], before_meta=[near_site()])
        self.assertNotIn(self.c.id, self.ids("ceo.crew"))

    def test_assigned_to_me_comes_first_and_payload_has_location(self):
        other = self.make_concern(title="Isa pang lubak", lat=self.c.latitude + Decimal("0.02"), lng=self.c.longitude)  # ~2 km away: not a duplicate
        self.route_to_city(other)
        self.accept(other)
        cs.assign_person(other, self.user("ceo.desk"), person=self.user("ceo.staff"))
        r = self.api("ceo.crew").get("/api/v1/staff/field/jobs/").json()
        self.assertEqual(r[0]["id"], self.c.id)
        self.assertTrue(r[0]["assigned_to_me"])
        self.assertIsNotNone(r[0]["latitude"])
        self.assertFalse(r[1]["assigned_to_me"])


class ArriveTests(FieldBase):
    def test_check_in_at_site_counts_as_first_response(self):
        r = self.api("ceo.crew").post(f"/api/v1/staff/concerns/{self.c.id}/arrive/",
                                      {"latitude": 13.9413, "longitude": 121.6173, "accuracy": 8}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        v = SiteVisit.objects.get(case=self.c.case)
        self.assertLess(v.distance_m, 50)
        self.assertFalse(v.is_far)
        self.c.refresh_from_db()
        self.assertIsNotNone(self.c.case.responded_at)
        self.assertEqual(self.c.status, "in_progress")
        self.assertEqual(r.json()["case"]["visits"][0]["user"], "Mario Bautista")

    def test_check_in_far_from_pin_is_flagged_not_refused(self):
        v = cs.arrive(self.c, self.user("ceo.crew"), latitude=13.9512, longitude=121.6173, accuracy=10)  # ~1.1 km
        self.assertTrue(v.is_far)

    def test_offline_check_in_keeps_phone_time(self):
        Case.objects.filter(pk=self.c.case.pk).update(routed_at=timezone.now() - timedelta(days=1))
        self.c.refresh_from_db()
        t = timezone.now() - timedelta(hours=2)
        v = cs.arrive(self.c, self.user("ceo.crew"), latitude=13.9412, longitude=121.6173, at=t)
        self.assertTrue(v.sent_offline)
        self.c.case.refresh_from_db()
        self.assertEqual(self.c.case.responded_at, t)

    def test_implausible_times_are_refused(self):
        for at in (timezone.now() + timedelta(hours=1), timezone.now() - timedelta(days=3)):
            with self.assertRaises(cs.WorkflowError):
                cs.arrive(self.c, self.user("ceo.crew"), at=at)

    def test_second_visit_does_not_move_first_response(self):
        cs.arrive(self.c, self.user("ceo.crew"), latitude=13.9412, longitude=121.6173)
        first = Case.objects.get(pk=self.c.case.pk).responded_at
        cs.arrive(self.c, self.user("ceo.staff"), latitude=13.9412, longitude=121.6173)
        self.assertEqual(Case.objects.get(pk=self.c.case.pk).responded_at, first)
        self.assertEqual(SiteVisit.objects.filter(case=self.c.case).count(), 2)

    def test_worker_from_another_office_cannot_check_in(self):
        r = self.api("gso.crew").post(f"/api/v1/staff/concerns/{self.c.id}/arrive/", {}, format="json")
        self.assertIn(r.status_code, (403, 404))


class BlockerTests(FieldBase):
    def test_blocker_alerts_office_leads_and_clears_on_completion(self):
        r = self.api("ceo.crew").post(f"/api/v1/staff/concerns/{self.c.id}/blocker/",
                                      {"reason": "materials", "remarks": "Walang cold mix"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["case"]["blocked_reason"], "materials")
        self.assertTrue(StaffAlert.objects.filter(kind="blocked", user=self.user("ceo.rdb.chief")).exists())
        self.assertFalse(StaffAlert.objects.filter(kind="blocked", user=self.user("ceo.crew")).exists())
        cs.complete_work(self.c, self.user("ceo.crew"), remarks="Tapos", photos=[jpeg(2)], photo_meta=[near_site()],
                         before_photos=[jpeg(1)], before_meta=[near_site()])
        self.c.case.refresh_from_db()
        self.assertEqual(self.c.case.blocked_reason, "")

    def test_wrong_office_also_tells_pacd(self):
        cs.report_blocker(self.c, self.user("ceo.crew"), reason="wrong_office")
        self.assertTrue(StaffAlert.objects.filter(kind="blocked", user=self.user("pacd.desk")).exists())

    def test_other_reason_needs_remarks(self):
        r = self.api("ceo.crew").post(f"/api/v1/staff/concerns/{self.c.id}/blocker/", {"reason": "other"}, format="json")
        self.assertEqual(r.status_code, 400)


class LivePhotoTests(FieldBase):
    def test_live_photo_at_site_gets_good_flag(self):
        cs.inspect(self.c, self.user("ceo.crew"), findings="Lubak", photos=[jpeg(7)],
                   photo_meta=[{**near_site(0.0002), "live": True}])
        a = self.c.attachments.get(kind="before")
        self.assertIn("live", a.flags)

    def test_live_claim_without_location_gets_no_good_flag(self):
        cs.inspect(self.c, self.user("ceo.crew"), findings="Lubak", photos=[jpeg(8)], photo_meta=[{"live": True}])
        self.assertNotIn("live", self.c.attachments.get(kind="before").flags)

    def test_live_photo_far_away_stays_red(self):
        cs.inspect(self.c, self.user("ceo.crew"), findings="Lubak", photos=[jpeg(9)],
                   photo_meta=[{**near_site(0.01), "live": True}])
        flags = self.c.attachments.get(kind="before").flags
        self.assertIn("far", flags)
        self.assertNotIn("live", flags)
