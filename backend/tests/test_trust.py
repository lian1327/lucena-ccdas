"""Report screening (Step 17): signals help the PACD; they never reject a report on their own."""
import json
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.cases import services as cs
from apps.concerns import trust
from apps.concerns.models import Concern
from apps.notifications.models import Notification
from apps.priority.services import distinct_duplicate_reporters

from .base import SITE, CCADSSTestCase, jpeg

URL = "/api/v1/public/concerns/"


class PhotoSignalTests(CCADSSTestCase):
    def report(self, img, meta=None, **kw):
        c = self.make_concern(submit=False, **kw)
        trust.save_citizen_photos(c, [img], [meta or {}])
        trust.assess(c)
        c.refresh_from_db()
        return c, c.attachments.get(kind="report")

    def test_plain_photo_without_camera_data_is_not_flagged(self):
        c, a = self.report(jpeg(1))
        self.assertEqual(a.flags, [])
        self.assertEqual(c.review_flags, [])

    def test_same_photo_for_a_different_place_is_red(self):
        self.report(jpeg(7))
        c, a = self.report(jpeg(7), lat=SITE[0] + Decimal("0.02"), category=self.light)
        self.assertEqual(a.flags, ["c_reused"])
        self.assertIn("c_reused", c.review_flags)

    def test_same_photo_shared_by_neighbours_is_only_info(self):
        self.report(jpeg(8))
        c, a = self.report(jpeg(8), lat=SITE[0] + Decimal("0.0005"))
        self.assertEqual(a.flags, ["c_shared"])
        self.assertNotIn("c_shared", c.review_flags)  # not worth a badge on the report

    def test_camera_gps_far_from_pin(self):
        _, a = self.report(jpeg(2), {"exif_lat": float(SITE[0]) + 0.03, "exif_lng": float(SITE[1])})
        self.assertIn("c_far", a.flags)

    def test_camera_gps_near_pin_is_clean(self):
        _, a = self.report(jpeg(3), {"exif_lat": float(SITE[0]) + 0.002, "exif_lng": float(SITE[1])})
        self.assertEqual(a.flags, [])

    def test_old_photo_date(self):
        old = (timezone.now() - timedelta(days=60)).isoformat()
        recent = (timezone.now() - timedelta(days=10)).isoformat()
        self.assertIn("c_old", self.report(jpeg(4), {"exif_time": old})[1].flags)
        self.assertNotIn("c_old", self.report(jpeg(5), {"exif_time": recent})[1].flags)

    def test_live_capture_at_the_site_is_a_good_sign(self):
        meta = {"device_lat": float(SITE[0]) + 0.0005, "device_lng": float(SITE[1]), "device_accuracy": 12, "live": True}
        c, a = self.report(jpeg(6), meta)
        self.assertEqual(a.flags, ["c_live"])
        self.assertIn("c_live", c.review_flags)

    def test_phone_location_far_away_is_not_called_far(self):
        meta = {"device_lat": float(SITE[0]) + 0.05, "device_lng": float(SITE[1]), "live": True}
        self.assertEqual(self.report(jpeg(9), meta)[1].flags, [])  # phone location isn't the photo's location


class PublicSubmitTests(CCADSSTestCase):
    def test_photo_meta_travels_with_the_upload_and_report_stays_submitted(self):
        api = APIClient()
        meta = [{"exif_lat": float(SITE[0]) + 0.03, "exif_lng": float(SITE[1])}]
        r = api.post(URL, {"description": "Malaking butas sa kalsada malapit sa paaralan", "category": "road_damage",
                           "barangay": self.brgy.pk, "location_description": "tapat ng paaralan",
                           "latitude": str(SITE[0]), "longitude": str(SITE[1]),
                           "reporter_name": "Juan", "reporter_contact": "09171234567", "consent_given": "true",
                           "images": [jpeg(11)], "photo_meta": json.dumps(meta)}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        c = Concern.objects.get(reference_no=r.json()["reference_no"])
        self.assertEqual(c.status, Concern.Status.SUBMITTED)  # a flag never rejects
        self.assertIn("c_far", c.review_flags)
        self.assertTrue(c.reporter_key and c.submit_ip_hash)
        self.assertNotIn("0917", c.reporter_key)

    def test_flags_reach_the_staff_api(self):
        c = self.make_concern(submit=False)
        trust.save_citizen_photos(c, [jpeg(12)], [{"exif_time": (timezone.now() - timedelta(days=90)).isoformat()}])
        trust.assess(c)
        api = APIClient()
        api.force_authenticate(self.user("pacd.desk"))
        row = api.get(f"/api/v1/staff/concerns/{c.pk}/").json()
        self.assertEqual(row["review_flags"][0]["code"], "c_old")
        self.assertTrue(any(f["code"] == "c_old" for f in row["attachments"][0]["flags"]))


class ReporterSignalTests(CCADSSTestCase):
    def unfounded(self, c):
        cs.mark_unfounded(c, self.user("pacd.desk"), remarks="Walang butas sa lugar nang puntahan.")

    def test_three_unfounded_then_flagged(self):
        for i in range(3):
            c = self.make_concern(lat=SITE[0] + Decimal(i) / 100, contact="09175550001")
            c.reporter_key = trust.reporter_key(c)
            c.save()
            self.unfounded(c)
        nxt = self.make_concern(contact="0917 555 0001", submit=False)
        nxt.reporter_key = trust.reporter_key(nxt)
        nxt.save()
        self.assertIn("repeat_unfounded", trust.assess(nxt))
        other = self.make_concern(contact="09175550002", submit=False, category=self.light)
        other.reporter_key = trust.reporter_key(other)
        other.save()
        self.assertNotIn("repeat_unfounded", trust.assess(other))

    def test_anonymous_reports_have_no_key(self):
        self.assertEqual(trust.reporter_key(self.make_concern(anonymous=True, submit=False)), "")

    def test_burst_from_one_network(self):
        api = APIClient()
        refs = []
        for i in range(4):
            r = api.post(URL, {"description": f"Baradong kanal bilang {i}, umaapaw tuwing ulan", "category": "drainage",
                               "barangay": self.brgy.pk, "location_description": f"kanto {i}", "is_anonymous": True,
                               "consent_given": True}, format="json")
            refs.append(r.json()["reference_no"])
        flags = [Concern.objects.get(reference_no=x).review_flags for x in refs]
        self.assertNotIn("burst", flags[2])
        self.assertIn("burst", flags[3])


class UnfoundedOutcomeTests(CCADSSTestCase):
    def test_needs_a_note_and_tells_the_reporter(self):
        with self.committed():
            c = self.make_concern()
            with self.assertRaises(cs.WorkflowError):
                cs.mark_unfounded(c, self.user("pacd.desk"), remarks="wala")
            cs.mark_unfounded(c, self.user("pacd.desk"), remarks="Walang butas nang inspeksyunin noong Lunes.")
        c.refresh_from_db()
        self.assertEqual((c.status, c.rejection_kind), (Concern.Status.REJECTED, "unfounded"))
        sms = c.notifications.get(event=Notification.Event.REJECTED, channel="sms")
        self.assertIn("hindi natagpuan", sms.body)

    def test_only_the_original_counts_against_the_reporter(self):
        master = self.make_concern(contact="09170000001")
        dup = self.make_concern(contact="09170000002")
        cs.mark_unfounded(master, self.user("pacd.desk"), remarks="Walang nakitang problema sa lugar.")
        dup.refresh_from_db()
        self.assertEqual(dup.status, Concern.Status.REJECTED)
        self.assertEqual(dup.rejection_kind, "")

    def test_field_staff_can_mark_unfounded_through_the_api(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.accept(c)
        cs.assign_person(c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        api = APIClient()
        api.force_authenticate(self.user("ceo.crew"))
        r = api.post(f"/api/v1/staff/concerns/{c.pk}/unfounded/", {"remarks": "Pinuntahan, walang butas sa lugar."},
                     format="json")
        self.assertEqual(r.status_code, 200, r.content)
        api.force_authenticate(self.user("mayor"))
        self.assertIn(api.post(f"/api/v1/staff/concerns/{self.make_concern(category=self.light).pk}/unfounded/",
                               {"remarks": "Walang problema sa lugar."}, format="json").status_code, (400, 403, 404))

    def test_report_card(self):
        c = self.make_concern()
        cs.mark_unfounded(c, self.user("pacd.desk"), remarks="Walang nakitang problema sa lugar.")
        r = trust.report_card()
        self.assertEqual((r["decided"], r["unfounded"]), (1, 1))


class AnonymousCapTests(CCADSSTestCase):
    def test_many_anonymous_duplicates_count_as_two(self):
        master = self.make_concern(contact="09170000001")
        for _ in range(5):
            self.make_concern(anonymous=True)
        self.assertEqual(distinct_duplicate_reporters(master), 2)
        self.make_concern(contact="09170000009")
        self.assertEqual(distinct_duplicate_reporters(master), 3)
