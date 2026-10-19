"""Staff-side workflow (Module 2: Case Management). Views call these; nothing else mutates cases."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.concerns.models import Concern, ConcernAttachment, StatusHistory
from apps.concerns.services import change_status
from apps.priority.services import compute_priority

from . import deadlines
from .models import Case, CaseNote, Endorsement, EndorsementFollowUp

S = Concern.Status
FOLLOW_UP_DAYS = 7


class WorkflowError(Exception):
    pass


def _name(u):
    return (u.get_full_name() or u.username) if u else "System"


def _note(case, user, body):
    if case:
        CaseNote.objects.create(case=case, author=user, body=body)


def _public_entry(concern, user, remarks):
    """Public timeline message without a status change (e.g. deadline extension, endorsement follow-up)."""
    StatusHistory.objects.create(
        concern=concern, from_status=concern.status, to_status=concern.status,
        remarks=remarks, is_public=True, changed_by=user,
    )
    for dup in concern.duplicates.all():
        StatusHistory.objects.create(
            concern=dup, from_status=dup.status, to_status=dup.status,
            remarks=f"Kasama sa report {concern.reference_no}. {remarks}", is_public=True, changed_by=user,
        )


def _attach(concern, user, photos, kind=ConcernAttachment.Kind.RESOLUTION):
    for f in photos:
        ConcernAttachment.objects.create(concern=concern, file=f, uploaded_by=user, kind=kind)


def _move(concern, user, status, remarks, is_public=True):
    """Status change that tolerates the case already being at that status (then it's a timeline message)."""
    if concern.status != status:
        change_status(concern, status, user, remarks, is_public=is_public, enforce=False)
    elif is_public and remarks:
        _public_entry(concern, user, remarks)


# ---------------- Intake ----------------

@transaction.atomic
def verify(concern, user, *, category, subcategory=None, severity, remarks=""):
    """Triage: confirm labels. From here on the concern counts in analytics."""
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


def suggested_route(concern):
    """Default office/division from the sub-type, else the category."""
    sub, cat = concern.subcategory, concern.category
    dept = (sub.default_department if sub else None) or (cat.default_department if cat else None)
    div = sub.default_division if (sub and sub.default_division and dept and sub.default_division.department_id == dept.id) else None
    return dept, div


@transaction.atomic
def route(concern, user, *, level, department=None, division=None, remarks=""):
    """PACD / barangay sends the concern to who will handle it. Starts the ARTA clock."""
    if level == Case.Level.EXTERNAL:
        raise WorkflowError("Use the endorsement action for external agencies.")
    if level == Case.Level.CITY and not department:
        department, division = suggested_route(concern)
        if not department:
            raise WorkflowError("Pick an office: this category has no default office.")
    if department and department.is_external:
        raise WorkflowError("That is an external agency. Use 'Endorse' instead.")
    if division and department and division.department_id != department.id:
        raise WorkflowError("Division does not belong to the selected office.")

    case = getattr(concern, "case", None)
    now = timezone.now()
    due = deadlines.initial_due(concern, now)
    fields = dict(level=level, department=department if level == Case.Level.CITY else None,
                  division=division if level == Case.Level.CITY else None,
                  assigned_to=None, assigned_by=user)
    if case is None:
        case = Case.objects.create(concern=concern, due_at=due, original_due_at=due, **fields)
    else:
        moved = (case.level, case.department_id) != (level, fields["department"].id if fields["department"] else None)
        for k, v in fields.items():
            setattr(case, k, v)
        if moved:  # new owner gets a fresh ARTA clock
            case.due_at = case.original_due_at = due
            case.extended_at = None
            case.extension_reason = ""
            case.inspected_at = case.work_completed_at = None
        case.save()
        _note(case, user, f"Inilipat sa {department.name if department else 'barangay'}. {remarks}".strip())

    where = department.name if level == Case.Level.CITY else f"Barangay {concern.barangay.name}"
    msg = remarks or f"Naipasa na sa {where}. Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}."
    if concern.status in (S.SUBMITTED, S.UNDER_REVIEW):
        change_status(concern, S.ASSIGNED, user, msg)
    else:
        _move(concern, user, S.ASSIGNED, msg)
    compute_priority(concern)
    return case


# ---------------- Inside the office ----------------

@transaction.atomic
def assign_division(concern, user, *, division, remarks=""):
    case = concern.case
    if division.department_id != case.department_id:
        raise WorkflowError("Division does not belong to this office.")
    case.division = division
    if case.assigned_to and case.assigned_to.division_id not in (None, division.id):
        case.assigned_to = None
    case.save(update_fields=["division", "assigned_to"])
    _note(case, user, f"Ipinasa sa {division.name}. {remarks}".strip())
    return case


@transaction.atomic
def assign_person(concern, user, *, person, remarks=""):
    case = concern.case
    if person.department_id != case.department_id:
        raise WorkflowError("This person is not in the handling office.")
    case.assigned_to = person
    case.assigned_by = user
    if not case.division_id and person.division_id:
        case.division_id = person.division_id
    case.save(update_fields=["assigned_to", "assigned_by", "division"])
    _note(case, user, f"Itinalaga kay {_name(person)}. {remarks}".strip())
    return case


@transaction.atomic
def inspect(concern, user, *, findings, action_plan="", scheduled_for=None, public_message=""):
    """Site inspection → findings + plan + schedule. Citizen is told when work is scheduled (Charter step 'inform client')."""
    case = concern.case
    case.inspected_at = timezone.now()
    case.inspected_by = user
    case.inspection_findings = findings
    case.action_plan = action_plan
    case.scheduled_for = scheduled_for
    case.save(update_fields=["inspected_at", "inspected_by", "inspection_findings", "action_plan", "scheduled_for"])
    msg = public_message or (
        f"Na-inspeksyon na ang lugar. Nakaiskedyul ang trabaho sa {scheduled_for:%b %d, %Y}."
        if scheduled_for else "Na-inspeksyon na ang lugar. Inihahanda ang trabaho."
    )
    _move(concern, user, S.IN_PROGRESS, msg)
    return case


@transaction.atomic
def complete_work(concern, user, *, remarks, photos):
    """Field reports the work done, with proof. Citizen still sees 'In Progress' until a supervisor validates."""
    if not photos and getattr(settings, "REQUIRE_RESOLUTION_PHOTO", True):
        raise WorkflowError("Attach at least one photo of the completed work.")
    case = concern.case
    _attach(concern, user, photos)
    case.work_completed_at = timezone.now()
    case.work_completed_by = user
    case.completion_remarks = remarks
    case.save(update_fields=["work_completed_at", "work_completed_by", "completion_remarks"])
    _move(concern, user, S.IN_PROGRESS, "Natapos na ang trabaho; hinihintay ang beripikasyon ng supervisor.", is_public=False)
    _note(case, user, f"Work reported complete: {remarks}")
    return case


@transaction.atomic
def validate(concern, user, *, approve, remarks="", photos=()):
    """Supervisor confirms (→ Resolved, shown to citizen) or sends it back to the crew."""
    case = concern.case
    if not approve:
        if not remarks:
            raise WorkflowError("Explain what still needs to be done.")
        case.work_completed_at = None
        case.work_completed_by = None
        case.save(update_fields=["work_completed_at", "work_completed_by"])
        _note(case, user, f"Returned to field: {remarks}")
        return case

    _attach(concern, user, photos)
    has_proof = concern.attachments.filter(kind=ConcernAttachment.Kind.RESOLUTION).exists()
    if not has_proof and getattr(settings, "REQUIRE_RESOLUTION_PHOTO", True):
        raise WorkflowError("A resolution photo is required before marking this resolved.")
    public = remarks or case.completion_remarks or "Naayos na ang iyong report. Salamat!"
    now = timezone.now()
    case.validated_at = now
    case.validated_by = user
    case.resolution_summary = public
    case.resolved_at = now
    if not case.work_completed_at:  # external agency / admin shortcut
        case.work_completed_at = now
    case.save(update_fields=["validated_at", "validated_by", "resolution_summary", "resolved_at", "work_completed_at"])
    _move(concern, user, S.RESOLVED, public)
    return case


@transaction.atomic
def extend_deadline(concern, user, *, new_due, reason):
    """ARTA: one extension, before the original lapses, not longer than the original period; citizen notified."""
    case = concern.case
    now = timezone.now()
    if case.extended_at:
        raise WorkflowError("This case was already extended once (ARTA allows one extension).")
    if case.due_at and now > case.due_at:
        raise WorkflowError("The original deadline has already lapsed; extensions must be filed before it.")
    limit = deadlines.max_extension_due(case)
    if new_due <= case.due_at or new_due > limit:
        raise WorkflowError(f"New date must be after the current deadline and no later than {timezone.localtime(limit):%b %d, %Y}.")
    case.original_due_at = case.original_due_at or case.due_at
    case.due_at = new_due
    case.extended_at = now
    case.extension_reason = reason
    case.save(update_fields=["original_due_at", "due_at", "extended_at", "extension_reason"])
    _public_entry(concern, user, f"Na-extend ang target na petsa sa {timezone.localtime(new_due):%b %d, %Y}. Dahilan: {reason}")
    return case


# ---------------- External endorsement (e.g. DPWH) ----------------

@transaction.atomic
def endorse(concern, user, *, agency, letter_reference="", contact_person="", remarks=""):
    if not agency.is_external:
        raise WorkflowError("Pick an external agency.")
    now = timezone.now()
    case = getattr(concern, "case", None)
    if case is None:
        case = Case.objects.create(concern=concern, level=Case.Level.EXTERNAL, department=agency, assigned_by=user)
    else:
        _note(case, user, f"Endorsed out from {case.department.name if case.department else 'barangay'} to {agency.name}.")
        case.level = Case.Level.EXTERNAL
        case.department = agency
        case.division = None
        case.assigned_to = None
    # LGU's own ARTA clock: monitoring/feedback continues even if the agency is slow
    case.due_at = case.original_due_at = deadlines.initial_due(concern, now)
    case.extended_at = None
    case.save()
    Endorsement.objects.create(
        case=case, agency=agency, endorsed_by=user, letter_reference=letter_reference,
        contact_person=contact_person, next_follow_up_at=now + timedelta(days=FOLLOW_UP_DAYS),
    )
    msg = remarks or (
        f"Ang lugar ay sakop ng {agency.name}. Inendorso na ito ng City Hall"
        f"{f' (Ref. {letter_reference})' if letter_reference else ''} at patuloy naming susubaybayan."
    )
    if concern.status in (S.SUBMITTED, S.UNDER_REVIEW):
        change_status(concern, S.ASSIGNED, user, msg)
    else:
        _move(concern, user, S.ASSIGNED, msg)
    return case


@transaction.atomic
def endorsement_follow_up(concern, user, *, method, notes, status=None, agency_response="", public_message=""):
    case = concern.case
    e = case.endorsements.filter(agency=case.department).first()
    if not e:
        raise WorkflowError("No active endorsement.")
    EndorsementFollowUp.objects.create(endorsement=e, by=user, method=method, notes=notes)
    e.follow_up_count += 1
    e.next_follow_up_at = timezone.now() + timedelta(days=FOLLOW_UP_DAYS)
    if status:
        e.status = status
    if agency_response:
        e.agency_response = agency_response
    e.save()
    if status == Endorsement.Status.SCHEDULED:
        _move(concern, user, S.IN_PROGRESS, public_message or f"Nakaiskedyul na ng {e.agency.name} ang aksyon.")
    elif public_message:
        _public_entry(concern, user, public_message)
    return e


# ---------------- 8888 ----------------

@transaction.atomic
def record_8888_feedback(concern, user, *, feedback):
    """'Concrete and specific' action report back to the 8888 focal person (EO 6 s. 2016)."""
    concern.external_feedback = feedback
    concern.external_feedback_sent_at = timezone.now()
    concern.save(update_fields=["external_feedback", "external_feedback_sent_at", "updated_at"])
    if hasattr(concern, "case"):
        _note(concern.case, user, f"8888 feedback sent: {feedback}")
    return concern


# ---------------- Generic ----------------

@transaction.atomic
def reject(concern, user, *, remarks):
    change_status(concern, S.REJECTED, user, remarks)


@transaction.atomic
def close(concern, user, *, remarks=""):
    change_status(concern, S.CLOSED, user, remarks or "Isinara na ang report. Salamat sa pakikipagtulungan!")


@transaction.atomic
def reopen(concern, user, *, remarks):
    case = concern.case
    case.work_completed_at = case.validated_at = case.resolved_at = None
    case.work_completed_by = case.validated_by = None
    case.save(update_fields=["work_completed_at", "validated_at", "resolved_at", "work_completed_by", "validated_by"])
    change_status(concern, S.IN_PROGRESS, user, remarks)


@transaction.atomic
def escalate(concern, user, *, reason, auto=False):
    case = concern.case
    if case.escalation_level >= Case.EscalationLevel.MAYOR:
        return case
    case.escalation_level += 1
    case.escalated_at = timezone.now()
    case.escalation_reason = reason
    case.save(update_fields=["escalation_level", "escalated_at", "escalation_reason"])
    who = "System (lumampas sa target na petsa)" if auto else _name(user)
    _note(case, user, f"Escalated to {case.get_escalation_level_display()} by {who}: {reason}")
    compute_priority(concern)
    return case


def escalate_overdue(now=None):
    """
    Run hourly. Open cases past due escalate one level (Dept Head → City Admin → Mayor) and get a
    short grace window so they don't escalate every hour.
    """
    now = now or timezone.now()
    overdue = Case.objects.select_related("concern__category").filter(
        concern__status__in=Concern.OPEN_STATUSES,
        concern__duplicate_of__isnull=True,
        due_at__lt=now,
        escalation_level__lt=Case.EscalationLevel.MAYOR,
    )
    n = 0
    for case in overdue:
        escalate(case.concern, None, reason=f"Lumampas sa target na petsa ({timezone.localtime(case.due_at):%b %d}).", auto=True)
        case.due_at = deadlines.add_working_days(now, 2)
        case.save(update_fields=["due_at"])
        n += 1
    return n


@transaction.atomic
def link_duplicate(concern, master, user):
    if master.pk == concern.pk or master.duplicate_of_id:
        raise WorkflowError("Pick the original (master) report, not another duplicate.")
    concern.duplicate_of = master
    concern.save(update_fields=["duplicate_of", "updated_at"])
    for d in concern.duplicates.all():
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
