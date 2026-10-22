"""Deployment endpoints: health check, site mode, the token-protected job runner, and public sample-data rules."""
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.notifications.models import StaffAlert

from .base import CCADSSTestCase


class SystemEndpointTests(CCADSSTestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def test_health(self):
        r = self.api.get("/api/v1/health/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    @override_settings(CCADSS_SITE_MODE="prototype")
    def test_site_mode_prototype(self):
        self.assertEqual(self.api.get("/api/v1/public/site/").json()["mode"], "prototype")

    @override_settings(CCADSS_SITE_MODE="anything-else")
    def test_unknown_mode_falls_back_to_prototype(self):
        self.assertEqual(self.api.get("/api/v1/public/site/").json()["mode"], "prototype")

    @override_settings(CCADSS_CRON_TOKEN="s3cret")
    def test_cron_needs_the_token(self):
        self.assertEqual(self.api.post("/api/v1/internal/cron/").status_code, 403)
        self.assertEqual(self.api.post("/api/v1/internal/cron/", HTTP_X_CRON_TOKEN="wrong").status_code, 403)
        r = self.api.post("/api/v1/internal/cron/", HTTP_X_CRON_TOKEN="s3cret")
        self.assertEqual(r.status_code, 200)
        self.assertIn("escalated", r.json())

    @override_settings(CCADSS_CRON_TOKEN="")
    def test_cron_disabled_without_a_token(self):
        self.assertEqual(self.api.post("/api/v1/internal/cron/", HTTP_X_CRON_TOKEN="").status_code, 403)


class SampleDataTests(CCADSSTestCase):
    def setUp(self):
        cache.clear()
        self.make_concern(is_synthetic=True)
        self.api = APIClient()

    @override_settings(CCADSS_PUBLIC_SAMPLE_DATA=False)
    def test_sample_data_hidden_from_public_numbers(self):
        self.assertEqual(self.api.get("/api/v1/public/stats/").json()["totals"]["total"], 0)
        self.assertFalse(self.api.get("/api/v1/public/site/").json()["sample_data"])

    @override_settings(CCADSS_PUBLIC_SAMPLE_DATA=True)
    def test_sample_data_shown_and_flagged(self):
        self.assertEqual(self.api.get("/api/v1/public/stats/").json()["totals"]["total"], 1)
        self.assertTrue(self.api.get("/api/v1/public/site/").json()["sample_data"])

    def test_sample_data_never_alerts_staff(self):
        c = self.make_concern(is_synthetic=True, category=self.light, lat=None, lng=None, danger_now=True)
        self.route_to_city(c)
        self.assertFalse(StaffAlert.objects.filter(concern=c).exists())
