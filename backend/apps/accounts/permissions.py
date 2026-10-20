from rest_framework.permissions import BasePermission

from .models import User

R = User.Role
STAFF_ROLES = (R.PACD, R.BARANGAY, R.OFFICE_DESK, R.DEPT_HEAD, R.DIVISION_CHIEF, R.DEPT_STAFF, R.CITY_ADMIN, R.MAYOR)
DEPARTMENT_ROLES = (R.OFFICE_DESK, R.DEPT_HEAD, R.DIVISION_CHIEF, R.DEPT_STAFF)
EXECUTIVE_ROLES = (User.Role.CITY_ADMIN, User.Role.MAYOR)


def HasRole(*roles):
    """Usage: permission_classes = [HasRole(*STAFF_ROLES)]"""

    class _HasRole(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and (u.is_superuser or u.role in roles))

    _HasRole.__name__ = "HasRole_" + "_".join(roles)
    return _HasRole
