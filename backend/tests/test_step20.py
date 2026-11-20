"""Step 20: national-road endorsement suggestion, AI-source markers, ocular verification, job acceptance,
public work report and reply."""
import io
import json
import os
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics import kpis
from apps.cases import credentials, services as cs
from apps.cases.models import Case
from apps.concerns.models import Category
from apps.concerns.trust import save_citizen_photos
from apps.geo.models import Road
from apps.geo.roads import nearest_road
from apps.notifications.models import StaffAlert

from .base import SITE, CCADSSTestCase, jpeg, near_site

LAT, LNG = float(SITE[0]), float(SITE[1])
# a north-south national road 10 m east of the test site
ROAD = {"type": "LineString", "coordinates": [[LNG + 0.00009, LAT - 0.01], [LNG + 0.00009, LAT + 0.01]]}


def api(user):
    a = APIClient()
    a.force_authenticate(user)
    return a


class RoadTests(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"name": "Maharlika Highway", "ref": "N1"}, "geometry": ROAD},
            {"type": "Feature", "properties": {"name": "Purok road", "ref": ""}, "geometry": {
                "type": "LineString", "coordinates": [[LNG - 0.001, LAT], [LNG - 0.002, LAT]]}},
        ]}
        fd, self.path = tempfile.mkstemp(suffix=".geojson")
        with os.fdopen(fd, "w") as f:
            json.dump(fc, f)

    def tearDown(self):
        os.remove(self.path)
        super().tearDown()

    def test_osm_import_keeps_national_routes_only(self):
        call_command("import_roads", self.path, "--osm", stdout=io.StringIO())
        self.assertEqual(Road.objects.count(), 1)
        road, d = nearest_road(LAT, LNG)
        self.assertEqual(road.ref, "N1")
        self.assertLess(d, 15)
        self.assertEqual(nearest_road(LAT, LNG + 0.002), (None, None))  # ~200 m away

    def test_streetlight_on_national_road_suggests_meralco(self):
        call_command("import_roads", self.path, "--osm", stdout=io.StringIO())
        light = Category.objects.get(code="streetlight")
        c = self.make_concern(category=light, title="Patay ang ilaw sa highway")
        data = api(self.user("pacd.desk")).get(f"/api/v1/staff/concerns/{c.id}/").json()
        s = data["endorse_suggestion"]
        self.assertEqual(s["agency_code"], "ELEC")
        self.assertIn("Meralco", s["agency_name"])
        self.assertIn("Maharlika", s["reason"])

    def test_off_the_national_road_no_suggestion(self):
        call_command("import_roads", self.path, "--osm", stdout=io.StringIO())
        light = Category.objects.get(code="streetlight")
        c = self.make_concern(category=light, lng=LNG - 0.0015)  # on the purok road, 170 m from the highway
        self.assertIsNone(cs.endorse_suggestion(c))

    def test_road_damage_on_national_road_suggests_dpwh(self):
        call_command("import_roads", self.path, "--osm", stdout=io.StringIO())
        self.assertEqual(cs.endorse_suggestion(self.make_concern())["agency_code"], "DPWH")


class AiMarkerTests(CCADSSTestCase):
    def test_markers_in_file_bytes(self):
        gen = b"<Iptc4xmpExt:DigitalSourceType>http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia<"
        self.assertEqual(credentials.scan_bytes(b"\xff\xd8" + gen), "ai_generated")
        self.assertEqual(credentials.scan_bytes(b"...compositeWithTrainedAlgorithmicMedia..."), "ai_edited")
        self.assertEqual(credentials.scan_bytes(b"..jumb....c2pa.."), "credentials")
        self.assertIsNone(credentials.scan_bytes(jpeg(1).read()))

    def test_citizen_photo_declared_ai_is_red_and_never_live(self):
        c = self.make_concern(submit=False)
        save_citizen_photos(c, [jpeg(3)], [{**near_site(), "live": True, "ai_marker": "ai_generated"}])
        from apps.concerns.trust import assess

        flags = assess(c)
        self.assertIn("c_ai", flags)
        self.assertNotIn("c_live", flags)

    def test_staff_photo_with_ai_marker_is_red_and_not_ocular(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.accept(c)
        cs.inspect(c, self.user("ceo.crew"), findings="x", photos=[jpeg(4)], photo_meta=[{**near_site(), "ai_marker": "ai_generated"}])
        self.assertIn("ai", c.attachments.get(kind="before").flags)
        c.case.refresh_from_db()
        self.assertIsNone(c.case.ocular_verified_at)


class OcularTests(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        self.c = self.make_concern()
        self.route_to_city(self.c)
        self.accept(self.c)
        cs.assign_person(self.c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        self.c.refresh_from_db()

    def test_check_in_at_the_site_verifies(self):
        cs.arrive(self.c, self.user("ceo.crew"), latitude=LAT + 0.0003, longitude=LNG, accuracy=10)  # ~33 m
        self.c.case.refresh_from_db()
        self.assertEqual(self.c.case.ocular_method, "checkin")

    def test_check_in_far_away_does_not(self):
        cs.arrive(self.c, self.user("ceo.crew"), latitude=LAT + 0.01, longitude=LNG, accuracy=10)  # ~1.1 km
        self.c.case.refresh_from_db()
        self.assertIsNone(self.c.case.ocular_verified_at)

    def test_clean_before_photo_at_the_site_verifies(self):
        cs.inspect(self.c, self.user("ceo.crew"), findings="Lubak", photos=[jpeg(5)], photo_meta=[near_site()])
        self.c.case.refresh_from_db()
        self.assertEqual(self.c.case.ocular_method, "photo")

    def test_unfounded_after_a_visit_is_measured(self):
        cs.arrive(self.c, self.user("ceo.crew"), latitude=LAT, longitude=LNG, accuracy=5)
        cs.mark_unfounded(self.c, self.user("ceo.crew"), remarks="Walang lubak sa lugar.")
        start, end = timezone.now() - timedelta(days=1), timezone.now() + timedelta(days=1)
        rows, _ = kpis.scorecard(start, end)
        ceo = next(r for r in rows if r["code"] == "CEO")
        self.assertEqual(ceo["ocular_verified"], 1)
        self.assertEqual(ceo["unfounded_on_site"], 1)
        self.assertEqual(ceo["unfounded_on_site_rate"], 1.0)


class TakeJobTests(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        self.c = self.make_concern()
        self.route_to_city(self.c)
        self.accept(self.c)
        cs.assign_person(self.c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        self.c.refresh_from_db()

    def test_only_the_assigned_lead_can_accept(self):
        r = api(self.user("ceo.staff")).post(f"/api/v1/staff/concerns/{self.c.id}/take-job/")
        self.assertEqual(r.status_code, 403)
        r = api(self.user("ceo.crew")).post(f"/api/v1/staff/concerns/{self.c.id}/take-job/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()["case"]["worker_accepted_at"])

    def test_arriving_counts_as_accepting(self):
        cs.arrive(self.c, self.user("ceo.crew"), latitude=LAT, longitude=LNG)
        self.c.case.refresh_from_db()
        self.assertIsNotNone(self.c.case.worker_accepted_at)

    def test_reassigning_resets_acceptance(self):
        cs.take_job(self.c, self.user("ceo.crew"))
        cs.assign_person(self.c, self.user("ceo.desk"), person=self.user("ceo.staff"))
        self.c.case.refresh_from_db()
        self.assertIsNone(self.c.case.worker_accepted_at)

    def test_chief_is_reminded_once_when_not_accepted_in_time(self):
        Case.objects.filter(pk=self.c.case.pk).update(person_assigned_at=timezone.now() - timedelta(hours=50))  # P4: 48 h
        self.assertEqual(cs.remind_unaccepted(), 1)
        self.assertTrue(StaffAlert.objects.filter(kind="not_accepted", user=self.user("ceo.rdb.chief")).exists())
        self.assertFalse(StaffAlert.objects.filter(kind="not_accepted", user=self.user("ceo.crew")).exists())
        self.assertEqual(cs.remind_unaccepted(), 0)

    def test_not_reminded_before_the_time(self):
        self.assertEqual(cs.remind_unaccepted(), 0)


class PublicAccountabilityTests(CCADSSTestCase):
    def setUp(self):
        super().setUp()
        self.c = self.make_concern()
        self.route_to_city(self.c)
        self.accept(self.c)
        cs.assign_person(self.c, self.user("ceo.desk"), person=self.user("ceo.crew"))
        cs.complete_work(self.c, self.user("ceo.crew"), remarks="Tinapalan ng cold mix ang lubak.", photos=[jpeg(2)],
                         photo_meta=[near_site()], before_photos=[jpeg(1)], before_meta=[near_site()])
        self.url = f"/api/v1/public/concerns/track/{self.c.reference_no}/"

    def test_work_summary_only_after_validation_and_without_names(self):
        self.assertIsNone(APIClient().get(self.url).json()["work_summary"])
        cs.validate(self.c, self.user("ceo.rdb.chief"), approve=True)
        body = APIClient().get(self.url).json()
        ws = body["work_summary"]
        self.assertEqual(ws["what_was_done"], "Tinapalan ng cold mix ang lubak.")
        self.assertIn("City Engineering", ws["done_by"])
        self.assertNotIn("Mario", json.dumps(body))

    def test_team_replies_in_public(self):
        cs.validate(self.c, self.user("ceo.rdb.chief"), approve=True)
        r = api(self.user("ceo.crew")).post(f"/api/v1/staff/concerns/{self.c.id}/public-reply/",
                                            {"message": "Pansamantalang tapal muna; full repair sa Disyembre."}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        timeline = APIClient().get(self.url).json()["timeline"]
        reply = next(t for t in timeline if t["remarks"].startswith("Tugon ng"))
        self.assertIn("City Engineering", reply["remarks"])
        self.assertNotIn("Mario", reply["remarks"])

    def test_other_office_cannot_reply(self):
        r = api(self.user("gso.crew")).post(f"/api/v1/staff/concerns/{self.c.id}/public-reply/",
                                            {"message": "x"}, format="json")
        self.assertIn(r.status_code, (403, 404))
