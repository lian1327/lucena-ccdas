"""Staff-side workflow (Module 2: Case Management). Views call these; nothing else mutates cases."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.concerns.models import Concern, ConcernAttachment, StatusHistory
from apps.concerns.services import change_status
from apps.notifications import services as notify
from apps.notifications.models import Notification, StaffAlert
from apps.priority.services import compute_priority

from . import deadlines, evidence
from .models import AccomplishmentReport, Case, CaseNote, Endorsement, EndorsementFollowUp, PriorityLevel

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


def _attach(concern, user, photos, kind=ConcernAttachment.Kind.RESOLUTION, meta=(), report=None):
    """Save staff photos with their evidence metadata and run the proof checks on each."""
    case = getattr(concern, "case", None)
    meta = list(meta or [])
    before_hashes = []
    if kind == ConcernAttachment.Kind.RESOLUTION:
        before_hashes = list(concern.attachments.filter(kind=ConcernAttachment.Kind.BEFORE)
                             .exclude(phash="").values_list("phash", flat=True))
    saved = []
    for i, f in enumerate(photos):
        m = evidence.build_metadata(f, meta[i] if i < len(meta) else {})
        att = ConcernAttachment(
            concern=concern, file=f, uploaded_by=user, kind=kind, report=report,
            latitude=evidence.to_decimal(m["latitude"]), longitude=evidence.to_decimal(m["longitude"]),
            gps_source=m["gps_source"], gps_accuracy_m=m["gps_accuracy_m"],
            taken_at=m["taken_at"], time_source=m["time_source"], phash=m["phash"],
        )
        att.uploaded_at = timezone.now()
        evidence.check(att, case, before_hashes)
        att.save()
        saved.append(att)
    return saved


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


def suggest_priority(concern):
    """
    Starting point for the office's judgment (they confirm or change it on acceptance):
      P1 Emergency  – citizen reported danger, or verified severity ≥ 4 on a safety-weighted category
      P2 Urgent     – priority score ≥ 50 (many affected / many reporters / severe)
      P3 Standard   – score ≥ 20
      P4 Low        – everything else
    """
    levels = {p.code: p for p in PriorityLevel.objects.all()}
    if not levels:
        return None
    score = float(concern.priority_score or 0)
    if concern.danger_now or (concern.is_verified and concern.severity >= 5):
        code = "P1"
    elif score >= 50 or concern.severity >= 4:
        code = "P2"
    elif score >= 20:
        code = "P3"
    else:
        code = "P4"
    return levels.get(code) or next(iter(levels.values()))


def _apply_clocks(case, start=None, keep_extension=False):
    """(Re)compute response and resolution targets from the clock start and the case's priority level."""
    start = start or case.routed_at or timezone.now()
    concern = case.concern
    if not (keep_extension and case.extended_at):
        case.due_at = case.original_due_at = deadlines.resolution_due(concern, start, case.priority_level)
    case.response_due_at = None if case.responded_at else deadlines.response_due(start, case.priority_level)


@transaction.atomic
def route(concern, user, *, level, department=None, division=None, remarks=""):
    """
    PACD / barangay sends the concern to who will handle it. Starts the clocks.
    City-level cases wait for the office's own receiving & screening (accept or return) within 1 working day.
    """
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

    city = level == Case.Level.CITY
    now = timezone.now()
    case = getattr(concern, "case", None)
    if case is None:
        case = Case(concern=concern)
    elif case.department_id or case.level == Case.Level.BARANGAY:
        _note(case, user, f"Inilipat sa {department.name if city else 'barangay'}. {remarks}".strip())

    case.level = level
    case.department = department if city else None
    case.division = division if city else None
    case.assigned_to = None
    case.assigned_by = user
    case.routed_at = now
    case.extended_at = None
    case.extension_reason = ""
    case.inspected_at = case.work_completed_at = case.responded_at = None
    case.accepted_at = None if city else now          # barangay-level: the barangay routed it to itself
    case.accepted_by = None if city else user
    case.acceptance_due_at = deadlines.acceptance_due(now) if city else None
    case.screening = {}
    case.priority_level = case.priority_level or suggest_priority(concern)
    _apply_clocks(case, now)
    case.save()

    where = department.name if city else f"Barangay {concern.barangay.name}"
    msg = remarks or f"Naipasa na sa {where}. Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}."
    if concern.status in (S.SUBMITTED, S.UNDER_REVIEW):
        change_status(concern, S.ASSIGNED, user, msg)
    else:
        _move(concern, user, S.ASSIGNED, msg)
    compute_priority(concern)
    if city:
        notify.alert(notify.office_leads(case), StaffAlert.Kind.NEW_CASE, concern,
                     f"Bagong kaso: {concern.reference_no}", f"{concern.title}. Tanggapin o ibalik sa loob ng 1 working day.",
                     urgent=concern.danger_now, exclude=user)
    else:
        from apps.accounts.models import User

        notify.alert(User.objects.filter(is_active=True, role=User.Role.BARANGAY, barangay_id=concern.barangay_id),
                     StaffAlert.Kind.NEW_CASE, concern, f"Bagong kaso sa barangay: {concern.reference_no}",
                     concern.title, urgent=concern.danger_now, exclude=user)
    return case


# ---------------- Office receiving & screening ----------------

@transaction.atomic
def accept(concern, user, *, priority_level, screening=None, division=None, priority_reason="", remarks=""):
    """
    The receiving office confirms the case is theirs, answers its own screening checklist, and confirms the
    priority level. Changing the suggested level requires a reason (it changes the citizen's target date).
    """
    case = concern.case
    if case.accepted_at:
        raise WorkflowError("Already accepted.")
    if division and division.department_id != case.department_id:
        raise WorkflowError("Division does not belong to this office.")
    checklist = case.department.screening_checklist or []
    answers = screening or {}
    missing = [q for q in checklist if q not in answers]
    if missing:
        raise WorkflowError(f"Sagutin ang lahat ng screening questions ({len(missing)} pa).")
    changed = case.priority_level_id != priority_level.id
    if changed and not priority_reason.strip():
        raise WorkflowError("Give a reason for changing the suggested priority level.")

    now = timezone.now()
    case.accepted_at = now
    case.accepted_by = user
    case.screening = answers
    if division:
        case.division = division
    if changed:
        old = case.priority_level
        case.priority_level = priority_level
        case.priority_reason = priority_reason
        _apply_clocks(case)  # clock still runs from receipt, not from acceptance
        _note(case, user, f"Priority {old.code if old else '—'} → {priority_level.code}: {priority_reason}")
    case.save()
    _note(case, user, f"Tinanggap ng {case.department.code}. {remarks}".strip())
    msg = f"Tinanggap na ng {case.department.name}. Antas: {priority_level.name_fil or priority_level.name}. " \
          f"Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}."
    _public_entry(concern, user, msg)
    return case


@transaction.atomic
def return_to_pacd(concern, user, *, reason):
    """Wrong office: send back to the PACD with a reason (not straight to another office, to avoid ping-pong)."""
    case = concern.case
    if case.accepted_at:
        raise WorkflowError("Accepted cases are re-routed by PACD or the City Administrator.")
    dept = case.department
    case.returned_at = timezone.now()
    case.return_reason = f"{dept.code if dept else ''}: {reason}"
    case.return_count += 1
    case.department = None
    case.division = None
    case.assigned_to = None
    case.acceptance_due_at = None
    case.save()
    _note(case, user, f"Ibinalik sa PACD ng {dept.name if dept else 'opisina'}: {reason}")
    change_status(concern, S.UNDER_REVIEW, user, f"Returned by {dept.code if dept else 'office'}: {reason}",
                  is_public=False, enforce=False)
    notify.alert(notify.pacd_staff(), StaffAlert.Kind.RETURNED, concern, f"Ibinalik ng {dept.code if dept else 'opisina'}: {concern.reference_no}",
                 reason, exclude=user)
    return case


@transaction.atomic
def set_priority(concern, user, *, priority_level, reason):
    case = concern.case
    if case.priority_level_id == priority_level.id:
        return case
    old = case.priority_level
    case.priority_level = priority_level
    case.priority_reason = reason
    _apply_clocks(case, keep_extension=True)
    case.save()
    _note(case, user, f"Priority {old.code if old else '—'} → {priority_level.code}: {reason}")
    _public_entry(concern, user, f"Binago ang antas ng prayoridad: {priority_level.name_fil or priority_level.name}. "
                                 f"Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}.")
    return case


@transaction.atomic
def respond(concern, user, *, remarks, photos=(), photo_meta=()):
    """First field action / make-safe (e.g. barricade an open manhole). Stops the response clock."""
    case = concern.case
    if case.responded_at:
        raise WorkflowError("Response already logged.")
    case.responded_at = timezone.now()
    case.responded_by = user
    case.response_remarks = remarks
    case.save(update_fields=["responded_at", "responded_by", "response_remarks"])
    _attach(concern, user, photos, kind=ConcernAttachment.Kind.PROGRESS, meta=photo_meta)
    _move(concern, user, S.IN_PROGRESS, remarks)
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
    from apps.accounts.models import User

    notify.alert(User.objects.filter(is_active=True, division=division, role=User.Role.DIVISION_CHIEF),
                 StaffAlert.Kind.NEW_CASE, concern, f"Para sa {division.name}: {concern.reference_no}", concern.title,
                 exclude=user)
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
    due = f" Target: {timezone.localtime(case.due_at):%b %d}." if case.due_at else ""
    notify.alert([person], StaffAlert.Kind.ASSIGNED, concern, f"Itinalaga sa iyo: {concern.reference_no}",
                 f"{concern.title}.{due}", urgent=concern.danger_now, exclude=user)
    return case


@transaction.atomic
def inspect(concern, user, *, findings, action_plan="", scheduled_for=None, public_message="",
            photos=(), photo_meta=()):
    """Site inspection → findings + plan + schedule + BEFORE photos. Citizen is told when work is scheduled."""
    case = concern.case
    _attach(concern, user, photos, kind=ConcernAttachment.Kind.BEFORE, meta=photo_meta)
    case.inspected_at = timezone.now()
    case.inspected_by = user
    if not case.responded_at:  # site inspection counts as the first response
        case.responded_at = case.inspected_at
        case.responded_by = user
    case.inspection_findings = findings
    case.action_plan = action_plan
    case.scheduled_for = scheduled_for
    case.save(update_fields=["inspected_at", "inspected_by", "inspection_findings", "action_plan", "scheduled_for",
                             "responded_at", "responded_by"])
    msg = public_message or (
        f"Na-inspeksyon na ang lugar. Nakaiskedyul ang trabaho sa {scheduled_for:%b %d, %Y}."
        if scheduled_for else "Na-inspeksyon na ang lugar. Inihahanda ang trabaho."
    )
    _move(concern, user, S.IN_PROGRESS, msg)
    return case


@transaction.atomic
def complete_work(concern, user, *, remarks, photos, photo_meta=(), before_photos=(), before_meta=(),
                  started_at=None, finished_at=None, crew=(), other_workers="", materials=(), equipment=""):
    """
    Field reports the work done = an accomplishment report: what was done, who was there, what was used,
    plus BEFORE and AFTER photos with location/time. Citizen still sees 'In Progress' until a supervisor validates.
    """
    require = getattr(settings, "REQUIRE_RESOLUTION_PHOTO", True)
    if not photos and require:
        raise WorkflowError("Kailangan ng 'after' na litrato ng natapos na trabaho.")
    has_before = concern.attachments.filter(kind=ConcernAttachment.Kind.BEFORE).exists()
    if require and not has_before and not before_photos:
        raise WorkflowError("Kailangan ng 'before' na litrato (kuha bago simulan ang trabaho).")
    if started_at and finished_at and finished_at < started_at:
        raise WorkflowError("Mas maaga ang 'natapos' kaysa sa 'sinimulan'.")
    now = timezone.now()
    if finished_at and finished_at > now + timedelta(minutes=10):
        raise WorkflowError("Hindi puwedeng nasa hinaharap ang oras ng pagtatapos.")
    case = concern.case
    report = AccomplishmentReport.objects.create(
        case=case, submitted_by=user, work_done=remarks, started_at=started_at, finished_at=finished_at or now,
        other_workers=other_workers, equipment=equipment,
        materials=[m for m in (materials or []) if str(m.get("item", "")).strip()],
    )
    report.crew.set({*(crew or []), user})
    _attach(concern, user, before_photos, kind=ConcernAttachment.Kind.BEFORE, meta=before_meta, report=report)
    after = _attach(concern, user, photos, meta=photo_meta, report=report)
    case.work_completed_at = now
    case.work_completed_by = user
    case.completion_remarks = remarks
    case.save(update_fields=["work_completed_at", "work_completed_by", "completion_remarks"])
    _move(concern, user, S.IN_PROGRESS, "Natapos na ang trabaho; hinihintay ang beripikasyon ng supervisor.", is_public=False)
    reds = evidence.red_flags(after + list(concern.attachments.filter(kind=ConcernAttachment.Kind.BEFORE)))
    warn = f" ⚠ Photo checks: {', '.join(evidence.FLAGS[r][1] for r in reds)}." if reds else ""
    _note(case, user, f"Accomplishment report submitted: {remarks}{warn}")
    from apps.accounts.models import User

    validators = [u for u in notify.office_leads(case) if u.role != User.Role.OFFICE_DESK]
    notify.alert(validators, StaffAlert.Kind.FOR_VALIDATION, concern, f"Beripikahin: {concern.reference_no}",
                 "May accomplishment report na." + (" May red flag ang mga litrato." if reds else ""),
                 urgent=bool(reds), exclude=user)
    return case


@transaction.atomic
def validate(concern, user, *, approve, remarks="", photos=(), photo_meta=(), override_reason=""):
    """
    Supervisor confirms (→ Resolved, shown to citizen) or sends it back to the crew.
    If the photo checks raised a red flag, approval needs a written reason, recorded against the validator.
    """
    case = concern.case
    report = case.reports.filter(status=AccomplishmentReport.Status.SUBMITTED).first()
    now = timezone.now()
    if not approve:
        if not remarks:
            raise WorkflowError("Explain what still needs to be done.")
        notify.alert([case.work_completed_by, report.submitted_by if report else None, case.assigned_to],
                     StaffAlert.Kind.SENT_BACK, concern, f"Ibinalik ng supervisor: {concern.reference_no}", remarks,
                     exclude=user)
        case.work_completed_at = None
        case.work_completed_by = None
        case.save(update_fields=["work_completed_at", "work_completed_by"])
        if report:
            report.status, report.reviewed_by, report.reviewed_at, report.review_remarks = \
                AccomplishmentReport.Status.RETURNED, user, now, remarks
            report.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_remarks"])
        _note(case, user, f"Returned to field: {remarks}")
        return case

    _attach(concern, user, photos, meta=photo_meta, report=report)
    staff_photos = concern.attachments.filter(kind__in=[ConcernAttachment.Kind.BEFORE, ConcernAttachment.Kind.RESOLUTION])
    reds = evidence.red_flags(staff_photos)
    if reds and len((override_reason or "").strip()) < 15:
        raise WorkflowError(
            "May red flag ang mga litrato (" + "; ".join(evidence.FLAGS[r][1] for r in reds) + "). "
            "Isulat kung bakit aaprubahan pa rin (hal. 'Personal kong ininspeksyon kahapon; mahina ang GPS sa ilalim ng tulay')."
        )
    if report:
        report.status, report.reviewed_by, report.reviewed_at = AccomplishmentReport.Status.APPROVED, user, now
        report.review_remarks = remarks
        report.override_reason = override_reason.strip() if reds else ""
        report.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_remarks", "override_reason"])
    if reds:
        _note(case, user, f"Approved despite photo flags ({', '.join(reds)}): {override_reason.strip()}")
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
    notify.citizen_event(concern, Notification.Event.EXTENDED,
                         extra={"due": f"{timezone.localtime(new_due):%b %d}", "reason": reason})
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
def citizen_confirm(concern, *, fixed, feedback=""):
    """
    The reporter answers "Naayos ba talaga?" on the tracking page.
      fixed     → recorded; a resolved report is closed (loop closed by the citizen themself)
      not fixed → the case is reopened, the office is told, and it counts as a reopen in the office KPIs
    """
    if concern.citizen_confirmation:
        raise WorkflowError("Nakapagbigay ka na ng sagot para sa report na ito.")
    if concern.status not in (S.RESOLVED, S.CLOSED) or not concern.resolved_at:
        raise WorkflowError("Maaari lamang sumagot kapag naayos na ang report.")
    if timezone.now() - concern.resolved_at > timedelta(days=CONFIRM_WINDOW_DAYS):
        raise WorkflowError(f"Lampas na sa {CONFIRM_WINDOW_DAYS} araw mula nang maayos. Mag-report muli kung bumalik ang problema.")
    concern.citizen_confirmation = Concern.Confirmation.FIXED if fixed else Concern.Confirmation.NOT_FIXED
    concern.citizen_confirmed_at = timezone.now()
    concern.citizen_feedback = (feedback or "").strip()[:1000]
    concern.save(update_fields=["citizen_confirmation", "citizen_confirmed_at", "citizen_feedback", "updated_at"])
    if fixed:
        if concern.status == S.RESOLVED:
            change_status(concern, S.CLOSED, None, "Kinumpirma ng nag-report na naayos na. Salamat!",
                          enforce=False, cascade=False)
        return concern
    master = concern.duplicate_of or concern  # one reporter of a shared problem can reopen the shared case
    msg = "Ayon sa nag-report, HINDI pa naayos" + (f": {concern.citizen_feedback}" if concern.citizen_feedback else ".")
    case = getattr(master, "case", None)
    if case:
        case.work_completed_at = case.validated_at = case.resolved_at = None
        case.work_completed_by = case.validated_by = None
        case.save(update_fields=["work_completed_at", "validated_at", "resolved_at", "work_completed_by", "validated_by"])
        _note(case, None, f"Citizen disputed the fix ({concern.reference_no}). {msg}")
        notify.alert([case.assigned_to, *notify.office_leads(case)], StaffAlert.Kind.DISPUTED, master,
                     f"Hindi raw naayos: {master.reference_no}", concern.citizen_feedback or "Binuksan muli ng nag-report.",
                     urgent=True)
    change_status(master, S.IN_PROGRESS, None, msg + " Binuksan muli ang kaso.", enforce=False)
    if concern is not master and concern.status != S.IN_PROGRESS:
        change_status(concern, S.IN_PROGRESS, None, msg + " Binuksan muli ang kaso.", enforce=False, cascade=False)
    return concern


CONFIRM_WINDOW_DAYS = 30


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
    notify.alert(notify.escalation_targets(case), StaffAlert.Kind.ESCALATED, concern,
                 f"Escalated sa {case.get_escalation_level_display()}: {concern.reference_no}", reason,
                 urgent=True, exclude=user)
    return case


def breaches(case, now=None):
    """Which commitments this open case has missed right now (used for escalation and analytics)."""
    now = now or timezone.now()
    out = []
    if case.level == Case.Level.CITY and case.department_id and not case.accepted_at \
            and case.acceptance_due_at and case.acceptance_due_at < now:
        out.append(f"hindi pa tinatanggap ng {case.department.code} (due {timezone.localtime(case.acceptance_due_at):%b %d %H:%M})")
    if not case.responded_at and case.response_due_at and case.response_due_at < now:
        lvl = case.priority_level.code if case.priority_level else ""
        out.append(f"walang unang aksyon para sa {lvl} (due {timezone.localtime(case.response_due_at):%b %d %H:%M})")
    if case.due_at and case.due_at < now:
        out.append(f"lampas sa target na petsa ({timezone.localtime(case.due_at):%b %d})")
    return out


def escalate_overdue(now=None):
    """
    Run hourly (Task Scheduler / Celery beat). Any missed commitment (acceptance, response, resolution)
    escalates the case one level: Dept Head → City Admin → Mayor. Targets are never moved; a separate
    timer (next_escalation_at) waits 2 working days before escalating the same case again.
    """
    now = now or timezone.now()
    candidates = Case.objects.select_related("concern__category", "department", "priority_level").filter(
        concern__status__in=Concern.OPEN_STATUSES,
        concern__duplicate_of__isnull=True,
        escalation_level__lt=Case.EscalationLevel.MAYOR,
    ).exclude(next_escalation_at__gt=now)
    n = 0
    for case in candidates:
        missed = breaches(case, now)
        if not missed:
            continue
        reason = "; ".join(missed)
        escalate(case.concern, None, reason=reason[:1].upper() + reason[1:] + ".", auto=True)
        case.next_escalation_at = deadlines.add_working_days(now, 2)
        case.save(update_fields=["next_escalation_at"])
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
