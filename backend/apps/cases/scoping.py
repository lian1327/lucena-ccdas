"""
Who sees what, and who may do what. Every staff endpoint goes through this module.

Chain of responsibility (modeled on ARTA's PACD requirement and a city engineering Citizen's Charter):
  PACD / Action Center ─ receives, verifies, routes, closes the loop with the citizen, handles 8888 feedback
  Office receiving     ─ each office's own desk: screens the case (office checklist), accepts or returns it
                         to PACD within 1 working day, confirms the priority level, forwards to a division
  Department Head      ─ owns the office's cases, routes to a division, validates, endorses outside (e.g. DPWH)
  Division Chief       ─ assigns engineer/crew, validates completed work (two-person rule)
  Field personnel      ─ inspects, schedules, does the work, uploads proof
  Barangay personnel   ─ intake for their barangay; resolves barangay-level concerns
  City Administrator   ─ everything (oversight + override)
  Mayor's Office       ─ read-only oversight; top of the escalation ladder
"""
from django.db.models import Q

from apps.accounts.models import User
from apps.concerns.models import Concern

R = User.Role
S = Concern.Status


def _case(c):
    return getattr(c, "case", None)


def is_admin(u):
    return u.is_superuser or u.role == R.CITY_ADMIN


def default_department_q(dept_id):
    """Unrouted concerns whose sub-type (or else category) routes to this office by default."""
    return Q(subcategory__default_department_id=dept_id) | Q(
        subcategory__default_department__isnull=True, category__default_department_id=dept_id
    )


def scoped_concerns(user):
    qs = Concern.objects.select_related(
        "category", "subcategory", "barangay", "duplicate_of",
        "case__department", "case__division", "case__assigned_to",
    )
    if is_admin(user) or user.role in (R.MAYOR, R.PACD):
        return qs
    if user.role in (R.DEPT_HEAD, R.OFFICE_DESK) and user.department_id:
        return qs.filter(
            Q(case__department_id=user.department_id)
            | Q(case__isnull=True) & default_department_q(user.department_id)
            # cases this office endorsed out (e.g. to DPWH) stay visible so the office can monitor them
            | Q(case__endorsements__endorsed_by__department_id=user.department_id)
        ).distinct()
    # Divisions and field staff only see a case after their office has screened and accepted it.
    accepted = Q(case__accepted_at__isnull=False)
    if user.role == R.DIVISION_CHIEF and user.department_id:
        return qs.filter(accepted & (
            Q(case__division_id=user.division_id)
            | Q(case__department_id=user.department_id, case__division__isnull=True)
        ))
    if user.role == R.DEPT_STAFF:
        q = Q(case__assigned_to=user)
        if user.division_id:
            q |= Q(case__division_id=user.division_id)
        return qs.filter(accepted & q)
    if user.role == R.BARANGAY and user.barangay_id:
        # Complaints about barangay officials are never visible to barangay personnel.
        return qs.filter(barangay_id=user.barangay_id, involves_barangay_officials=False)
    return qs.none()


# ---------------- per-action permissions ----------------

def _in_dept(u, case):
    return bool(case and u.department_id and case.department_id == u.department_id)


def _in_div(u, case):
    return bool(case and u.division_id and case.division_id == u.division_id)


def _barangay_level_owner(u, c):
    case = _case(c)
    return u.role == R.BARANGAY and u.barangay_id == c.barangay_id and case and case.level == case.Level.BARANGAY


def _is_worker(u, c):
    """People who do the field work on this case."""
    case = _case(c)
    if not case or c.status not in (S.ASSIGNED, S.IN_PROGRESS):
        return False
    if case.level == case.Level.EXTERNAL or not case.accepted_at:
        return False
    if is_admin(u) or _barangay_level_owner(u, c):
        return True
    if u.role == R.DEPT_HEAD:
        return _in_dept(u, case)
    if u.role == R.DIVISION_CHIEF:
        return _in_div(u, case) or (_in_dept(u, case) and not case.division_id)
    if u.role == R.DEPT_STAFF:
        return case.assigned_to_id == u.id or _in_div(u, case)
    return False


def _endorsed_by_office(u, case):
    return bool(case and u.department_id and case.endorsements.filter(endorsed_by__department_id=u.department_id).exists())


def permissions_for(u, c):
    case = _case(c)
    open_ = c.status in Concern.OPEN_STATUSES
    readonly = u.role == R.MAYOR
    admin = is_admin(u)
    pacd = u.role == R.PACD
    head = u.role == R.DEPT_HEAD and (_in_dept(u, case) or (case is None))
    desk = u.role == R.OFFICE_DESK and (_in_dept(u, case) or (case is None))
    accepted = bool(case and case.accepted_at)
    awaiting_acceptance = bool(
        case and case.level == case.Level.CITY and case.department_id and not case.accepted_at
    )
    chief = u.role == R.DIVISION_CHIEF and (_in_div(u, case) or (_in_dept(u, case) and case and not case.division_id))
    brgy = u.role == R.BARANGAY and u.barangay_id == c.barangay_id
    external = bool(case and case.level == case.Level.EXTERNAL)
    brgy_level = bool(case and case.level == case.Level.BARANGAY)
    is_dup = bool(c.duplicate_of_id)

    p = {
        "can_act": not readonly,
        # Intake
        "verify": not readonly and open_ and not c.is_verified and not is_dup
        and (admin or pacd or head or desk or (brgy and (case is None or brgy_level))),
        "route": not readonly and not is_dup and c.status in (S.SUBMITTED, S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS)
        and (admin or pacd or (brgy and (case is None or brgy_level))),
        "route_any_office": admin or pacd,
        "endorse": not readonly and open_ and not is_dup and not external and (admin or pacd or head),
        # Office receiving & screening
        "accept": not readonly and open_ and not is_dup and awaiting_acceptance and (admin or head or desk),
        "return_to_pacd": not readonly and open_ and not is_dup and awaiting_acceptance and (admin or head or desk),
        "set_priority": not readonly and open_ and not is_dup and bool(case) and not external
        and (accepted or brgy_level) and (admin or head or desk or chief or (brgy and brgy_level)),
        # Inside the office
        "assign_division": not readonly and open_ and accepted and not external and not brgy_level
        and (admin or head or desk),
        "assign_person": not readonly and open_ and accepted and not external and not brgy_level
        and (admin or head or chief),
        "respond": not readonly and _is_worker(u, c) and not (case and case.responded_at),
        "inspect": not readonly and _is_worker(u, c) and not (case and case.work_completed_at),
        "complete": not readonly and _is_worker(u, c) and not (case and case.work_completed_at),
        "validate": False,
        "extend": not readonly and open_ and bool(case) and bool(case.due_at) and not case.extended_at
        and (accepted or brgy_level or external)
        and (admin or pacd or head or desk or chief or (brgy and brgy_level)),
        "escalate": not readonly and open_ and bool(case) and case.escalation_level < 3 and not is_dup,
        "reject": not readonly and open_ and not is_dup and (admin or pacd or head),
        "close": not readonly and c.status == S.RESOLVED and (admin or pacd or (brgy and brgy_level)),
        "reopen": not readonly and c.status == S.RESOLVED and (admin or pacd),
        "notes": not readonly and bool(case),
        "link": not readonly and open_,
        "feedback_8888": not readonly and c.channel == Concern.Channel.HOTLINE_8888 and (admin or pacd),
        "follow_up": not readonly and external and open_ and (
            admin or pacd or (u.role == R.DEPT_HEAD and _endorsed_by_office(u, case))
        ),
    }

    # Validation: confirms the fix before the citizen sees "Resolved". Never by the person who did the work.
    if not readonly and case and open_ and not is_dup:
        not_doer = admin or case.work_completed_by_id != u.id
        if external:
            p["validate"] = admin or pacd  # agency reports done → LGU confirms on site
        elif brgy_level:
            p["validate"] = brgy and case.work_completed_at is not None and not_doer
        else:
            p["validate"] = case.work_completed_at is not None and not_doer and (admin or head or chief)
    return p
