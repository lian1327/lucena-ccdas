"""Who sees what. Every staff endpoint starts from scoped_concerns(user)."""
from django.db.models import Q

from apps.accounts.models import User
from apps.concerns.models import Concern

R = User.Role


def scoped_concerns(user):
    qs = Concern.objects.select_related(
        "category", "subcategory", "barangay", "case__department", "case__assigned_to", "duplicate_of"
    )
    if user.is_superuser or user.role in (R.CITY_ADMIN, R.MAYOR):
        return qs
    if user.role == R.DEPT_STAFF and user.department_id:
        # Their office's cases, plus unassigned concerns whose category defaults to their office (to triage).
        return qs.filter(
            Q(case__department_id=user.department_id)
            | Q(case__isnull=True, category__default_department_id=user.department_id)
        )
    if user.role == R.BARANGAY and user.barangay_id:
        # Complaints about barangay officials are never visible to barangay personnel.
        return qs.filter(barangay_id=user.barangay_id, involves_barangay_officials=False)
    return qs.none()


def can_assign_any(user):
    return user.is_superuser or user.role == R.CITY_ADMIN


def can_act(user):
    """Mayor's office is read-only (oversight); everyone else in staff roles can work cases they can see."""
    return user.is_superuser or user.role in (R.CITY_ADMIN, R.DEPT_STAFF, R.BARANGAY)


def can_resolve(user):
    return user.is_superuser or user.role in (R.CITY_ADMIN, R.DEPT_STAFF)
