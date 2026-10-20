from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        PACD = "pacd", "Public Assistance & Complaints Desk"
        BARANGAY = "barangay", "Barangay Personnel"
        OFFICE_DESK = "office_desk", "Office Receiving Officer"
        DEPT_HEAD = "dept_head", "Department Head"
        DIVISION_CHIEF = "division_chief", "Division Chief / Supervisor"
        DEPT_STAFF = "dept_staff", "Field Personnel (Engineer / Crew)"
        CITY_ADMIN = "city_admin", "City Administrator"
        MAYOR = "mayor", "Mayor's Office"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN)
    contact_number = models.CharField(max_length=20, blank=True)
    barangay = models.ForeignKey("geo.Barangay", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="users")
    department = models.ForeignKey("cases.Department", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="staff")
    division = models.ForeignKey("cases.Division", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="staff")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
