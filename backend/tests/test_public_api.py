"""Citizen portal: validation, privacy of the tracking page, confirmation, SMS opt-out."""
from rest_framework.test import APIClient

from apps.concerns.models import Concern

from .base import CCADSSTestCase

BASE = "/api/v1/public/"


class SubmitTests(CCADSSTestCase):
    def payload(self, **kw):
        p = {"description": "Malaking butas sa kalsada sa tapat ng paaralan", "category": "road_damage",
             "barangay": self.brgy.pk, "location_description": "tapat ng elementary school",
             "reporter_name": "Juan Dela Cruz", "reporter_contact": "09171234567", "consent_given": True}
        p.update(kw)
        return p

    def setUp(self):
        self.api = APIClient()

    def test_submit_returns_reference(self):
        r = self.api.post(f"{BASE}concerns/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertRegex(r.json()["reference_no"], r"^CCD-\d{4}-[A-Z0-9]{6}$")
        self.assertNotIn("reporter_contact", r.json())

    def test_consent_is_required(self):
        r = self.api.post(f"{BASE}concerns/", self.payload(consent_given=False), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("consent_given", r.json())

    def test_invalid_mobile_is_rejected(self):
        r = self.api.post(f"{BASE}concerns/", self.payload(reporter_contact="12345"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("reporter_contact", r.json())

    def test_anonymous_report_drops_identity(self):
        r = self.api.post(f"{BASE}concerns/", self.payload(is_anonymous=True), format="json")
        c = Concern.objects.get(reference_no=r.json()["reference_no"])
        self.assertEqual((c.reporter_name, c.reporter_contact), ("", ""))

    def test_pin_outside_service_area_is_rejected(self):
        r = self.api.post(f"{BASE}concerns/", self.payload(latitude="35.0", longitude="139.0"), format="json")
        self.assertEqual(r.status_code, 400)


class TrackTests(CCADSSTestCase):
    def setUp(self):
        self.api = APIClient()
        self.c = self.make_concern(email="juan@example.com")

    def test_tracking_page_never_shows_personal_data(self):
        body = self.api.get(f"{BASE}concerns/track/{self.c.reference_no}/").content.decode()
        for secret in ("Juan Dela Cruz", "09171234567", "juan@example.com"):
            self.assertNotIn(secret, body)

    def test_unknown_reference_is_404(self):
        self.assertEqual(self.api.get(f"{BASE}concerns/track/CCD-2026-XXXXXX/").status_code, 404)

    def test_confirm_needs_last_four_digits(self):
        self.work_until_resolved(self.c)
        url = f"{BASE}concerns/track/{self.c.reference_no}/confirm/"
        self.assertEqual(self.api.post(url, {"fixed": True, "mobile_last4": "0000"}, format="json").status_code, 400)
        r = self.api.post(url, {"fixed": True, "mobile_last4": "4567"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["citizen_confirmation"], "fixed")

    def test_sms_opt_out(self):
        url = f"{BASE}concerns/track/{self.c.reference_no}/notifications/"
        self.assertEqual(self.api.post(url, {"sms": False, "mobile_last4": "1111"}, format="json").status_code, 400)
        r = self.api.post(url, {"sms": False, "mobile_last4": "4567"}, format="json")
        self.assertEqual(r.json()["sms_updates"], "off")
        self.c.refresh_from_db()
        self.assertFalse(self.c.notify_sms)

    def test_recent_fixes_show_no_reference_numbers(self):
        self.work_until_resolved(self.c)
        from django.core.cache import cache

        cache.clear()
        body = self.api.get(f"{BASE}recent-fixes/").content.decode()
        self.assertNotIn(self.c.reference_no, body)
