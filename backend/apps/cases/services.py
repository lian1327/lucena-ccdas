"""Staff-side workflow (Module 2: Case Management). Views call these; nothing else mutates cases."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.concerns.models import Concern, ConcernAttachment
from apps.concerns.services import change_status
from apps.priority.services import compute_priority

from .models import Case, CaseNote

S = Concern.Status


def _note(case, user, body):
    if case:
        CaseNote.objects.create(case=case, author=user, body=body)


@transaction.atomic
def verify(concern, user, *, category, subcategory=None, severity, remarks=""):
    """Triage: staff confirm the labels. From here on the concern counts in analytics."""
    concern.category = category
    concern.subcategory = subcategory
    concern.severity = severity
    concern.category_source = Concern.CategorySource.STAFF
    concern.is_verified = True
    concern.verified_by = user
    concern.verified_at = timezone.now()
    concern.save(update_fields=[
        "category", "subcategory", "severity", "category_source",
        "is_verified", "verified_by", "verified_at", "updated_at",
    ])
    if concern.status == S.SUBMITTED:
        change_status(concern, S.UNDER_REVIEW, user, remarks or "Sinuri na ng LGU ang iyong report.")
    else:
        compute_priority(concern)
    return concern


@transaction.atomic
def assign(concern, user, *, department, assigned_to=None, due_at=None, remarks=""):
    sla_days = (concern.category.sla_days if concern.category else None) or 7
    due_at = due_at or (timezone.now() + timedelta(days=sla_days))
    case, created = Case.objects.get_or_create(
        concern=concern,
        defaults=dict(department=department, assigned_to=assigned_to, assigned_by=user, due_at=due_at),
    )
    if not created:
        changed_dept = case.department_id != department.id
        case.department = department
        case.assigned_to = assigned_to
        case.assigned_by = user
        case.due_at = due_at
        case.save(update_fields=["department", "assigned_to", "assigned_by", "due_at"])
        if changed_dept:
            _note(case, user, f"Inilipat sa {department.name}. {remarks}".strip())

    public_msg = remarks or f"Naipasa na sa {department.name}."
    if concern.status in (S.SUBMITTED, S.UNDER_REVIEW):
        change_status(concern, S.ASSIGNED, user, public_msg)
    elif created or concern.status == S.IN_PROGRESS:
        change_status(concern, S.ASSIGNED, user, public_msg, enforce=False)
    return case


@transaction.atomic
def update_status(concern, user, *, status, remarks="", is_public=True, photos=()):
    """Field updates: in_progress / resolved / closed / rejected / reopen. Resolution photos are proof of fix."""
    case = getattr(concern, "case", None)
    if status == S.RESOLVED:
        for f in photos:
            ConcernAttachment.objects.create(
                concern=concern, file=f, uploaded_by=user, kind=ConcernAttachment.Kind.RESOLUTION
            )
        if case:
            case.resolution_summary = remarks
            case.resolved_at = timezone.now()
            case.save(update_fields=["resolution_summary", "resolved_at"])
    change_status(concern, status, user, remarks, is_public=is_public)
    return concern


@transaction.atomic
def escalate(concern, user, *, reason, auto=False):
    case = concern.case
    if case.escalation_level >= Case.EscalationLevel.MAYOR:
        return case
    case.escalation_level += 1
    case.escalated_at = timezone.now()
    case.escalation_reason = reason
    case.save(update_fields=["escalation_level", "escalated_at", "escalation_reason"])
    who = "System (lumampas sa SLA)" if auto else (user.get_full_name() or user.username)
    _note(case, user, f"Escalated to {case.get_escalation_level_display()} by {who}: {reason}")
    compute_priority(concern)
    return case


def escalate_overdue(now=None):
    """
    Run hourly (Celery beat / Task Scheduler): open cases past due get escalated one level,
    and get a fresh half-SLA window so they don't escalate again every hour.
    """
    now = now or timezone.now()
    grace = getattr(settings, "ESCALATION_GRACE_RATIO", 0.5)
    overdue = Case.objects.select_related("concern__category").filter(
        concern__status__in=Concern.OPEN_STATUSES,
        due_at__lt=now,
        escalation_level__lt=Case.EscalationLevel.MAYOR,
    )
    n = 0
    for case in overdue:
        escalate(case.concern, None, reason=f"Lumampas sa target na petsa ({case.due_at:%b %d}).", auto=True)
        sla = (case.concern.category.sla_days if case.concern.category else 7) or 7
        case.due_at = now + timedelta(days=max(sla * grace, 1))
        case.save(update_fields=["due_at"])
        n += 1
    return n


@transaction.atomic
def link_duplicate(concern, master, user):
    if master.pk == concern.pk or master.duplicate_of_id:
        raise ValueError("Pick the original (master) report, not another duplicate.")
    concern.duplicate_of = master
    concern.save(update_fields=["duplicate_of", "updated_at"])
    for d in concern.duplicates.all():  # re-point its own duplicates to the new master
        d.duplicate_of = master
        d.save(update_fields=["duplicate_of"])
    compute_priority(master)
    compute_priority(concern)


@transaction.atomic
def unlink_duplicate(concern, user):
    master = concern.duplicate_of
    concern.duplicate_of = None
    concern.save(update_fields=["duplicate_of", "updated_at"])
    if master:
        compute_priority(master)
    compute_priority(concern)
