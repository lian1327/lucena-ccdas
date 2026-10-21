"""SMS / email notifications and staff alerts."""
import io
import json
from datetime import datetime, timedelta
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.cases import services as cs
from apps.concerns.models import Concern
from apps.notifications import services as ns
from apps.notifications.messages import render_sms
from apps.notifications.models import Notification, StaffAlert
from apps.notifications.providers import SemaphoreProvider
from apps.notifications.sms import gsm_length, normalize_ph_mobile, segments, to_gsm

from .base import CCADSSTestCase

E = Notification.Event
N = Notification.Status


class SmsTextTests(CCADSSTestCase):
    def test_normalize_ph_numbers(self):
        for raw in ("09171234567", "0917 123 4567", "+639171234567", "639171234567", "0917-123-4567"):
            self.assertEqual(normalize_ph_mobile(raw), "639171234567", raw)
        for bad in ("", "12345", "0817123456", "02 8123 4567"):
            self.assertIsNone(normalize_ph_mobile(bad), bad)

    def test_gsm_conversion_keeps_filipino_letters(self):
        self.assertEqual(to_gsm("Señor “Juan” — salamat…"), 'Señor "Juan" - salamat...')
        self.assertEqual(gsm_length("a€"), 3)  # € is an extension character (2 units)

    def test_segments(self):
        self.assertEqual(segments("x" * 160), 1)
        self.assertEqual(segments("x" * 161), 2)
        self.assertEqual(segments("x" * 307), 3)

    def test_every_event_fits_one_sms(self):
        c = self.make_concern()
        self.route_to_city(c)
        c.refresh_from_db()
        for event in E.values:
            text = render_sms(c, event, extra={"due": "Nov 03", "reason": "Hinihintay ang materyales mula sa supplier"})
            self.assertLessEqual(gsm_length(text), 160, f"{event}: {text}")
            self.assertFalse(text.upper().startswith("TEST"))  # Semaphore drops these silently
            self.assertIn(c.reference_no, text)


class CitizenNotificationTests(CCADSSTestCase):
    def sms(self, c):
        return list(c.notifications.filter(channel="sms").order_by("created_at").values_list("event", flat=True))

    def test_received_sms_and_email_on_submit(self):
        with self.committed():
            c = self.make_concern(email="juan@example.com")
        self.assertEqual(self.sms(c), [E.RECEIVED])
        n = c.notifications.get(channel="sms")
        self.assertEqual((n.status, n.recipient, n.provider), (N.SENT, "639171234567", "console"))
        self.assertIn("https://ccadss.example.ph/t/" + c.reference_no, n.body)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(c.reference_no, mail.outbox[0].subject)

    def test_one_message_per_milestone_through_the_lifecycle(self):
        with self.committed():
            c = self.make_concern()
        with self.committed():
            self.work_until_resolved(c)
        self.assertEqual(self.sms(c), [E.RECEIVED, E.ASSIGNED, E.IN_PROGRESS, E.RESOLVED])

    def test_closing_after_citizen_confirms_sends_nothing_more(self):
        with self.committed():
            c = self.work_until_resolved(self.make_concern())
        n = c.notifications.count()
        with self.committed():
            cs.citizen_confirm(c, fixed=True)
        self.assertEqual(c.notifications.count(), n)

    def test_rejection_explains_why(self):
        with self.committed():
            c = self.make_concern()
            cs.reject(c, self.user("pacd.desk"), remarks="Pribadong lote ito, hindi sakop ng lungsod")
        body = c.notifications.get(event=E.REJECTED, channel="sms").body
        self.assertIn("Pribadong lote", body)

    def test_extension_notifies_with_new_date(self):
        from apps.cases import deadlines

        with self.committed():
            c = self.make_concern()
            case = self.route_to_city(c)
            cs.extend_deadline(c, self.user("ceo.head"), new_due=deadlines.max_extension_due(case), reason="Ulan")
        self.assertTrue(c.notifications.filter(event=E.EXTENDED, channel="sms").exists())

    def test_each_duplicate_reporter_gets_their_own_update(self):
        with self.committed():
            a = self.make_concern(contact="09170000001")
            b = self.make_concern(contact="09170000002")
        self.assertIn("pinagsama", b.notifications.get(event=E.RECEIVED).body)
        with self.committed():
            self.route_to_city(a)
        b_assigned = b.notifications.get(event=E.ASSIGNED)
        self.assertEqual(b_assigned.recipient, "639170000002")
        self.assertIn(b.reference_no, b_assigned.body)

    def test_no_sms_for_anonymous_opted_out_or_synthetic(self):
        with self.committed():
            anon = self.make_concern(anonymous=True)
            out = self.make_concern(contact="09170000003", notify_sms=False, category=self.light)
            fake = self.make_concern(contact="09170000004", is_synthetic=True, lat=None, lng=None)
        for c in (anon, out, fake):
            self.assertFalse(c.notifications.filter(channel="sms").exists())

    def test_muted_sends_nothing(self):
        with ns.muted(), self.committed():
            c = self.make_concern()
        self.assertFalse(c.notifications.exists())

    def test_same_update_is_never_sent_twice(self):
        with self.committed():
            c = self.make_concern()
        h = c.history.first()
        ns.queue(c, E.RECEIVED, history=h)
        self.assertEqual(c.notifications.filter(channel="sms").count(), 1)


class QuietHoursTests(CCADSSTestCase):
    def at(self, h, m=0):
        return timezone.make_aware(datetime(2026, 10, 20, h, m), timezone.get_current_timezone())

    @override_settings(CCADSS_SMS_QUIET_HOURS="21-7")
    def test_window(self):
        self.assertEqual(ns.next_allowed(self.at(14)), self.at(14))
        self.assertEqual(timezone.localtime(ns.next_allowed(self.at(22))).replace(tzinfo=None),
                         datetime(2026, 10, 21, 7, 0))
        self.assertEqual(timezone.localtime(ns.next_allowed(self.at(5))).replace(tzinfo=None),
                         datetime(2026, 10, 20, 7, 0))

    @override_settings(CCADSS_SMS_QUIET_HOURS="21-7")
    def test_night_report_waits_then_worker_sends(self):
        with mock.patch("apps.notifications.services.timezone.now", return_value=self.at(23)), self.committed():
            c = self.make_concern()
        n = c.notifications.get(channel="sms")
        self.assertEqual(n.status, N.QUEUED)
        self.assertEqual(ns.send_due(now=self.at(23, 30)), 0)
        self.assertEqual(ns.send_due(now=n.scheduled_for + timedelta(minutes=1)), 1)
        n.refresh_from_db()
        self.assertEqual(n.status, N.SENT)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class SemaphoreTests(CCADSSTestCase):
    def test_success_reply_is_parsed(self):
        reply = [{"message_id": 1234, "status": "Pending", "network": "Globe", "recipient": "639171234567"}]
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(json.dumps(reply).encode())) as m:
            r = SemaphoreProvider("KEY", "LUCENA").send("639171234567", "Natanggap ang report mo.")
        self.assertTrue(r.ok)
        self.assertEqual((r.message_id, r.status, r.network), ("1234", "Pending", "Globe"))
        sent = m.call_args[0][0]
        self.assertEqual(sent.full_url, "https://api.semaphore.co/api/v4/messages")
        self.assertIn(b"sendername=LUCENA", sent.data)
        self.assertIn(b"apikey=KEY", sent.data)

    def test_validation_error_is_a_failure(self):
        reply = {"number": ["The number format is invalid."]}
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(json.dumps(reply).encode())):
            r = SemaphoreProvider("KEY").send("639171234567", "x")
        self.assertFalse(r.ok)
        self.assertIn("invalid", r.error)

    def test_network_error_is_a_failure(self):
        import urllib.error

        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            r = SemaphoreProvider("KEY").send("639171234567", "x")
        self.assertFalse(r.ok)

    def test_missing_key_never_calls_out(self):
        with mock.patch("urllib.request.urlopen") as m:
            self.assertFalse(SemaphoreProvider("").send("639171234567", "x").ok)
        m.assert_not_called()


class RetryAndReminderTests(CCADSSTestCase):
    @override_settings(CCADSS_SMS_PROVIDER="disabled")
    def test_failed_sms_is_retried_with_backoff_and_capped(self):
        with self.committed():
            c = self.make_concern()
        n = c.notifications.get(channel="sms")
        self.assertEqual((n.status, n.attempts), (N.FAILED, 1))
        now = timezone.now()
        self.assertEqual(ns.retry_due(now=now + timedelta(minutes=1)), 0)     # waits 5 minutes
        self.assertEqual(ns.retry_due(now=now + timedelta(minutes=6)), 1)
        n.refresh_from_db()
        ns.retry_due(now=now + timedelta(minutes=30))
        n.refresh_from_db()
        self.assertEqual(n.attempts, 3)
        self.assertEqual(ns.retry_due(now=now + timedelta(hours=5)), 0)        # gives up after 3 tries

    def test_reminder_after_three_days_once(self):
        with self.committed():
            c = self.work_until_resolved(self.make_concern())
        Concern.objects.filter(pk=c.pk).update(resolved_at=timezone.now() - timedelta(days=4))
        self.assertGreaterEqual(ns.queue_reminders(), 1)
        self.assertEqual(ns.queue_reminders(), 0)
        self.assertIn("Naayos na ba talaga", c.notifications.get(event=E.REMINDER, channel="sms").body)

    def test_purge_blanks_old_recipients(self):
        with self.committed():
            c = self.make_concern()
        Notification.objects.filter(concern=c).update(created_at=timezone.now() - timedelta(days=400))
        self.assertGreaterEqual(ns.purge(365), 1)
        self.assertEqual(c.notifications.get(channel="sms").recipient, "")


class StaffAlertTests(CCADSSTestCase):
    def kinds(self, username):
        return list(StaffAlert.objects.filter(user=self.user(username)).values_list("kind", flat=True))

    def test_new_case_alerts_the_office_not_the_router(self):
        c = self.make_concern()
        self.route_to_city(c)
        self.assertIn("new_case", self.kinds("ceo.desk"))
        self.assertIn("new_case", self.kinds("ceo.head"))
        self.assertEqual(self.kinds("pacd.desk"), [])
        self.assertEqual(self.kinds("gso.desk"), [])

    def test_assignment_and_validation_alerts(self):
        self.work_until_resolved(self.make_concern())
        self.assertIn("assigned", self.kinds("ceo.crew"))
        self.assertIn("for_validation", self.kinds("ceo.rdb.chief"))

    def test_danger_report_alerts_pacd_urgently(self):
        self.make_concern(danger_now=True)
        a = StaffAlert.objects.get(user=self.user("pacd.desk"), kind="danger")
        self.assertTrue(a.is_urgent)

    def test_citizen_dispute_alerts_the_crew(self):
        c = self.work_until_resolved(self.make_concern())
        cs.citizen_confirm(c, fixed=False, feedback="May butas pa")
        self.assertIn("disputed", self.kinds("ceo.crew"))

    def test_bell_api_counts_and_marks_read(self):
        from rest_framework.test import APIClient

        self.route_to_city(self.make_concern())
        api = APIClient()
        api.force_authenticate(self.user("ceo.desk"))
        data = api.get("/api/v1/staff/alerts/").json()
        self.assertEqual(data["unread"], 1)
        api.post(f"/api/v1/staff/alerts/{data['results'][0]['id']}/read/")
        self.assertEqual(api.get("/api/v1/staff/alerts/").json()["unread"], 0)

    def test_people_only_see_their_own_alerts(self):
        from rest_framework.test import APIClient

        self.route_to_city(self.make_concern())
        alert = StaffAlert.objects.filter(user=self.user("ceo.desk")).first()
        api = APIClient()
        api.force_authenticate(self.user("gso.desk"))
        self.assertEqual(api.post(f"/api/v1/staff/alerts/{alert.pk}/read/").status_code, 404)


class LogApiTests(CCADSSTestCase):
    def test_log_is_masked_and_role_limited(self):
        from rest_framework.test import APIClient

        with self.committed():
            self.make_concern()
        api = APIClient()
        api.force_authenticate(self.user("pacd.desk"))
        rows = api.get("/api/v1/staff/notifications/").json()["results"]
        self.assertEqual(rows[0]["recipient"], "0917***4567")
        self.assertNotIn("09171234567", json.dumps(rows))
        api.force_authenticate(self.user("ceo.crew"))
        self.assertEqual(api.get("/api/v1/staff/notifications/").status_code, 403)
