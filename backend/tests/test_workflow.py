"""Module 2: the case lifecycle, ARTA extension rule, citizen confirmation and escalation."""
from datetime import timedelta

from django.utils import timezone

from apps.cases import services as cs
from apps.cases.models import Case
from apps.concerns.models import Concern
from apps.concerns.services import InvalidTransition, change_status

from .base import CCADSSTestCase

S = Concern.Status


class LifecycleTests(CCADSSTestCase):
    def test_full_path_submitted_to_closed(self):
        c = self.make_concern()
        self.assertEqual(c.status, S.SUBMITTED)
        c = self.work_until_resolved(c)
        self.assertEqual(c.status, S.RESOLVED)
        self.assertIsNotNone(c.resolved_at)
        cs.citizen_confirm(c, fixed=True)
        c.refresh_from_db()
        self.assertEqual(c.status, S.CLOSED)
        statuses = list(c.history.values_list("to_status", flat=True))
        for s in (S.SUBMITTED, S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED, S.CLOSED):
            self.assertIn(s, statuses)

    def test_invalid_transition_is_refused(self):
        c = self.make_concern()
        with self.assertRaises(InvalidTransition):
            change_status(c, S.CLOSED, self.user("pacd.desk"))

    def test_internal_steps_are_hidden_from_the_public_timeline(self):
        from rest_framework.test import APIClient

        c = self.make_concern()
        self.route_to_city(c)
        cs.return_to_pacd(c, self.user("ceo.desk"), reason="Internal: maling opisina")
        self.assertTrue(c.history.filter(is_public=False).exists())
        body = APIClient().get(f"/api/v1/public/concerns/track/{c.reference_no}/").content.decode()
        self.assertNotIn("maling opisina", body)

    def test_wrong_office_returns_to_pacd(self):
        c = self.make_concern()
        self.route_to_city(c)
        cs.return_to_pacd(c, self.user("ceo.desk"), reason="Hindi sa amin, DPWH road ito")
        c.refresh_from_db()
        self.assertEqual(c.status, S.UNDER_REVIEW)
        self.assertEqual(c.case.return_count, 1)
        self.assertIsNone(c.case.department_id)

    def test_screening_questions_must_be_answered(self):
        c = self.make_concern()
        case = self.route_to_city(c)
        if case.department.screening_checklist:
            with self.assertRaises(cs.WorkflowError):
                cs.accept(c, self.user("ceo.desk"), priority_level=case.priority_level, screening={})

    def test_changing_priority_needs_a_reason(self):
        from apps.cases.models import PriorityLevel

        c = self.make_concern()
        case = self.route_to_city(c)
        other = PriorityLevel.objects.exclude(pk=case.priority_level_id).first()
        answers = {q: "oo" for q in (case.department.screening_checklist or [])}
        with self.assertRaises(cs.WorkflowError):
            cs.accept(c, self.user("ceo.desk"), priority_level=other, screening=answers)


class ExtensionTests(CCADSSTestCase):
    def test_one_extension_only_and_within_limit(self):
        from apps.cases import deadlines

        c = self.make_concern()
        case = self.route_to_city(c)
        limit = deadlines.max_extension_due(case)
        with self.assertRaises(cs.WorkflowError):
            cs.extend_deadline(c, self.user("ceo.head"), new_due=limit + timedelta(days=5), reason="Kulang materyales")
        cs.extend_deadline(c, self.user("ceo.head"), new_due=limit, reason="Kulang materyales")
        with self.assertRaises(cs.WorkflowError):
            cs.extend_deadline(c, self.user("ceo.head"), new_due=limit + timedelta(days=1), reason="Ulit")

    def test_extension_after_deadline_lapsed_is_refused(self):
        c = self.make_concern()
        case = self.route_to_city(c)
        Case.objects.filter(pk=case.pk).update(due_at=timezone.now() - timedelta(hours=1))
        c.refresh_from_db()
        with self.assertRaises(cs.WorkflowError):
            cs.extend_deadline(c, self.user("ceo.head"), new_due=timezone.now() + timedelta(days=3), reason="Late")


class CitizenConfirmTests(CCADSSTestCase):
    def test_not_fixed_reopens_and_clears_validation(self):
        c = self.work_until_resolved(self.make_concern())
        cs.citizen_confirm(c, fixed=False, feedback="May butas pa sa gitna")
        c.refresh_from_db()
        self.assertEqual(c.status, S.IN_PROGRESS)
        self.assertIsNone(c.case.validated_at)
        self.assertEqual(c.citizen_confirmation, "not_fixed")

    def test_answer_only_once(self):
        c = self.work_until_resolved(self.make_concern())
        cs.citizen_confirm(c, fixed=True)
        c.refresh_from_db()
        with self.assertRaises(cs.WorkflowError):
            cs.citizen_confirm(c, fixed=False)

    def test_window_closes_after_30_days(self):
        c = self.work_until_resolved(self.make_concern())
        Concern.objects.filter(pk=c.pk).update(resolved_at=timezone.now() - timedelta(days=31))
        c.refresh_from_db()
        with self.assertRaises(cs.WorkflowError):
            cs.citizen_confirm(c, fixed=True)

    def test_duplicate_reporter_can_reopen_the_shared_case(self):
        master = self.make_concern()
        dup = self.make_concern(contact="09175550000")
        self.work_until_resolved(master)
        dup.refresh_from_db()
        self.assertEqual(dup.status, S.RESOLVED)
        cs.citizen_confirm(dup, fixed=False, feedback="Hindi pa po")
        master.refresh_from_db()
        self.assertEqual(master.status, S.IN_PROGRESS)


class EscalationTests(CCADSSTestCase):
    def test_overdue_case_escalates_one_level_at_a_time(self):
        c = self.make_concern()
        case = self.route_to_city(c)
        Case.objects.filter(pk=case.pk).update(acceptance_due_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(cs.escalate_overdue(), 1)
        case.refresh_from_db()
        self.assertEqual(case.escalation_level, Case.EscalationLevel.DEPARTMENT_HEAD)
        self.assertEqual(cs.escalate_overdue(), 0)  # waits 2 working days before the next level
