"""Proof of work: photo location, timing, reuse and before/after checks, and the override rule."""
from datetime import timedelta

from django.utils import timezone

from apps.cases import evidence
from apps.cases import services as cs
from apps.cases.models import AccomplishmentReport
from apps.concerns.models import Concern, ConcernAttachment

from .base import CCADSSTestCase, jpeg, near_site

K = ConcernAttachment.Kind


class HashTests(CCADSSTestCase):
    def test_same_image_same_hash_and_different_image_differs(self):
        a, b, c = evidence.dhash(jpeg(3)), evidence.dhash(jpeg(3)), evidence.dhash(jpeg(40))
        self.assertEqual(evidence.hamming(a, b), 0)
        self.assertGreater(evidence.hamming(a, c), evidence.REUSE_HAMMING)

    def test_missing_hash_is_maximally_different(self):
        self.assertEqual(evidence.hamming("", "abcd"), 64)


class FlagTests(CCADSSTestCase):
    def setUp(self):
        self.c = self.make_concern()
        self.case = self.route_to_city(self.c)

    def att(self, kind=K.RESOLUTION, meta=None, img=None, taken_at=None):
        f = img or jpeg(5)
        m = evidence.build_metadata(f, meta or {})
        a = ConcernAttachment(concern=self.c, file=f, kind=kind, latitude=evidence.to_decimal(m["latitude"]),
                              longitude=evidence.to_decimal(m["longitude"]), gps_source=m["gps_source"],
                              gps_accuracy_m=m["gps_accuracy_m"], taken_at=taken_at or m["taken_at"], phash=m["phash"])
        a.uploaded_at = timezone.now()
        return evidence.check(a, self.case)

    def test_photo_at_site_is_clean(self):
        self.assertEqual(self.att(meta=near_site(0.0003)).flags, [])

    def test_photo_far_from_site_is_red(self):
        a = self.att(meta=near_site(0.01))  # ≈ 1.1 km
        self.assertIn("far", a.flags)
        self.assertGreater(a.distance_m, 1000)

    def test_no_gps_is_amber_not_red(self):
        a = self.att(meta={})
        self.assertEqual(a.flags, ["no_gps"])
        self.assertEqual(evidence.red_flags([a]), [])

    def test_old_photo_is_stale(self):
        a = self.att(meta=near_site(), taken_at=timezone.now() - timedelta(days=5))
        self.assertIn("stale", a.flags)

    def test_after_photo_taken_before_routing_is_red(self):
        a = self.att(meta=near_site(), taken_at=self.case.routed_at - timedelta(days=2))
        self.assertIn("before_routing", a.flags)

    def test_after_identical_to_before_is_red(self):
        before = evidence.dhash(jpeg(9))
        a = self.att(meta=near_site(), img=jpeg(9))
        a = evidence.check(a, self.case, before_hashes=[before])
        self.assertIn("same_as_before", a.flags)

    def test_photo_reused_from_another_case_is_red(self):
        other = self.make_concern(category=self.light)
        ConcernAttachment.objects.create(concern=other, file=jpeg(11), kind=K.RESOLUTION, phash=evidence.dhash(jpeg(11)))
        a = self.att(meta=near_site(), img=jpeg(11))
        self.assertIn("reused", a.flags)


class AccomplishmentTests(CCADSSTestCase):
    def test_complete_requires_before_and_after_photos(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.accept(c)
        with self.assertRaises(cs.WorkflowError):
            cs.complete_work(c, self.user("ceo.crew"), remarks="Tapos", photos=[])
        with self.assertRaises(cs.WorkflowError):
            cs.complete_work(c, self.user("ceo.crew"), remarks="Tapos", photos=[jpeg(2)], photo_meta=[near_site()])

    def test_report_records_crew_and_is_approved(self):
        c = self.work_until_resolved(self.make_concern())
        r = AccomplishmentReport.objects.get(case=c.case)
        self.assertEqual(r.status, AccomplishmentReport.Status.APPROVED)
        self.assertIn(self.user("ceo.crew"), r.crew.all())
        self.assertEqual(r.reviewed_by, self.user("ceo.rdb.chief"))
        self.assertEqual(c.status, Concern.Status.RESOLVED)

    def test_red_flag_needs_a_written_reason(self):
        c = self.make_concern()
        with self.assertRaises(cs.WorkflowError):
            self.work_until_resolved(c, after_meta=near_site(0.02))
        c.refresh_from_db()
        self.assertNotEqual(c.status, Concern.Status.RESOLVED)
        cs.validate(c, self.user("ceo.rdb.chief"), approve=True,
                    override_reason="Personal kong ininspeksyon kahapon, mahina ang GPS sa lugar.")
        c.refresh_from_db()
        self.assertEqual(c.status, Concern.Status.RESOLVED)
        self.assertTrue(AccomplishmentReport.objects.get(case=c.case).override_reason)
